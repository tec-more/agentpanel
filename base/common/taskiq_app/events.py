"""事件分发任务（M3 完整实现，取代旧 ConsumerWorker）。

消费模型（对旧 ConsumerWorker._process_message 的语义平移 + 幂等补强）：
1. **消费端幂等（D6 / W3-1 闭环）**：`EventRecord.status` 终态（consumed /
   dead_letter）直接跳过——RabbitMQ at-least-once 重投、SmartRetry 重试、
   worker 多副本竞争都不会重复执行 handler。
2. **handler 来源 = 进程内 registry**（`EventBusAdapter.get_handlers`）。
   实施期发现：manifest `events.subscribe[].handler_ref` 指向的是**注册函数**
   （把真 handler 绑进总线），不是可直接执行的事件处理体，因此方案 B
   「DB 直接 resolve handler_ref 执行」对本代码库不成立；worker 须跑
   `event_center.initialize()`（register_ref + bind_manual）构建 registry，
   运行期插件启停由 worker 周期 `event_center.resync()` 收敛（见 jobs.py）。
3. **handler 执行**：逐个执行、单 handler 超时（`event_handler_timeout`）、
   异常隔离（一个失败不阻断其它）。
4. **重试语义**：失败未超上限 → EventRecord 置 failed 并**上抛异常**，
   由 broker 的 SmartRetryMiddleware 指数退避后重投（同消息重入 dispatch，
   非终态故会继续执行）；重试预算耗尽 → dead_letter 终态（可经重放接口恢复）。
   `--ack-type when_executed` 下消息本身在执行后 ACK，audit trail 以
   EventRecord 状态机为准。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger

from .broker import broker
from .config import settings
from .schema import EventMessage

# 消费端幂等：这些终态直接跳过（与旧 ConsumerWorker 语义对齐 + 跨进程生效）
_TERMINAL_STATUSES = frozenset({"consumed", "dead_letter"})


@broker.task(task_name="taskiq:dispatch", queue_name="ap.events")
async def dispatch(payload: Dict[str, Any]) -> None:
    """消费一条事件消息：幂等检查 → 执行 handlers → EventRecord 状态机。

    payload 为 dict（D7：跨进程只传 dict，不在边界传 BaseModel 实例）。
    """
    try:
        msg = EventMessage.model_validate(payload)
    except Exception as exc:  # 消息非法：记日志后返回（不重试，避免毒消息循环）
        logger.error(f"[taskiq:dispatch] 非法事件消息，已跳过: {exc}")
        return

    from base.common.events.models.event_record import EventRecord

    # ① 消费端幂等：终态直接跳过
    record = await EventRecord.get_or_none(event_uuid=msg.event_uuid)
    if record and record.status in _TERMINAL_STATUSES:
        logger.info(
            f"[taskiq:dispatch] 事件 {msg.event_uuid} 已终态({record.status})，跳过"
        )
        return

    # ② 进入消费态
    await EventRecord.filter(event_uuid=msg.event_uuid).update(status="consuming")

    # ③ 取 handler（进程内 registry；worker 启动期由 event_center.initialize 填充）
    from base.common.events.event_bus import event_bus

    handlers: List[Any] = event_bus.get_handlers(msg.event_name)
    if not handlers:
        await EventRecord.filter(event_uuid=msg.event_uuid).update(
            status="consumed",
            consumed_at=datetime.now(timezone.utc),
        )
        return

    start_time = datetime.now(timezone.utc)
    last_error: str | None = None
    for handler in handlers:
        try:
            result = handler(msg.event_name, **msg.payload)
            if asyncio.iscoroutine(result):
                await asyncio.wait_for(result, timeout=settings.event_handler_timeout)
        except Exception as exc:  # 单 handler 失败隔离，不阻断其它 handler
            last_error = str(exc)
            name = getattr(handler, "__name__", repr(handler))
            logger.error(f"[taskiq:dispatch] 事件 {msg.event_name} 处理器 {name} 执行失败: {exc}")

    # ④ 状态机：consumed / failed(上抛重试) / dead_letter(终态)
    if last_error is None:
        processing_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )
        await EventRecord.filter(event_uuid=msg.event_uuid).update(
            status="consumed",
            consumed_at=datetime.now(timezone.utc),
            processing_time_ms=processing_ms,
        )
        return

    # 失败：查重试预算（record 可能为 None——外部伪造 uuid；按 0 处理）
    retry_count = (record.retry_count if record else 0) + 1
    max_retries = _max_retries()
    await EventRecord.filter(event_uuid=msg.event_uuid).update(
        status="failed" if retry_count < max_retries else "dead_letter",
        retry_count=retry_count,
        error_message=last_error,
        next_retry_at=datetime.now(timezone.utc) if retry_count < max_retries else None,
    )
    if retry_count >= max_retries:
        logger.warning(
            f"[taskiq:dispatch] 事件 {msg.event_uuid} 超过最大重试次数({max_retries})，"
            f"进入 dead_letter（可经重放接口恢复）"
        )
        return
    # 未超上限：上抛 → SmartRetryMiddleware 退避后重投本任务（同 event_uuid，
    # 非终态 → 继续执行；再次失败时 retry_count 继续累计）
    raise RuntimeError(
        f"event {msg.event_uuid} handler failed (retry {retry_count}/{max_retries}): "
        f"{last_error}"
    )


def _max_retries() -> int:
    """最大重试次数：与旧链路同源（[rabbitmq] max_retries），下限 1。"""
    try:
        from base.common.setting import settings as app_settings

        return max(int(app_settings.RABBITMQ_MAX_RETRIES), 1)
    except Exception:
        return max(int(settings.retry_max), 1)
