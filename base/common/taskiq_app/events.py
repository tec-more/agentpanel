"""事件分发任务（Outbox/Inbox：事务化消息记录与状态修改）。

消费模型
--------
1. **事务①**：CAS 把消息记录从非终态推进到 ``consuming``（防止多副本并发
   双执行），并写 ``event_inbox`` 的 processing 凭据；已 ``done`` 的 handler
   直接跳过。终态（consumed / dead_letter）一律跳过 —— 覆盖 RabbitMQ
   at-least-once 重投、relay 崩溃重复投递、relay 对 failed 的退避补投。
2. **事务外执行 handler**：逐个执行、单 handler 超时、异常隔离。handler 可能
   含 HTTP / 跨库 / 30s 超时，**绝不能包进 DB 事务**；其副作用只能靠自身幂等
   与 Inbox 去重，这是最终一致的固有边界。同时记录每个 handler 的耗时、
   返回值（脱敏 + 限长）、异常类型与堆栈。
3. **事务②**：把每个 handler 的执行结果写回 Inbox，并按结果 CAS 把
   EventRecord 置为 consumed / failed / dead_letter。

重试模型（2026-11-15 修订，取代 SmartRetry 延迟重投）
----------------------------------------------------
失败**不再上抛**：``failed`` 状态与指数退避的 ``next_retry_at`` 已在事务②
持久化，由 ``platform:outbox_relay`` 到点补投（DB 状态机是真源）。原因：
``SmartRetryMiddleware.on_error`` 走 ``with_labels(delay=...)``，而本 broker
既未配 ``delay_queue`` 也未开 delayed-message-exchange，``AioPikaBroker.kick``
必然抛 ``IncorrectRoutingKeyError`` —— 旧链路「失败 → ack → 无人补投」实际是断的。
任务另加 ``retry_on_error=False`` label 作为双保险，避免两套重试并存导致双投。

状态允许集：relay 是「先投递、后改状态」，消息到达时 DB 可能仍是 pending，
所以 CAS 的 from_states 必须包含 pending / published / failed。
"""
from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger
from tortoise.transactions import in_transaction

from .broker import broker
from .config import settings
from .outbox import next_retry_at_for
from .schema import EventMessage

# 消费端幂等：这些终态直接跳过
_TERMINAL_STATUSES = frozenset({"consumed", "dead_letter"})
# 可被推进到 consuming 的状态。刻意**不含 consuming**：并发重复投递时第二个
# worker 的 CAS 必须失败，否则同一消息会被双执行。崩溃遗留的 consuming 由
# platform:stale_consuming_reap 先改回 pending 才会重新投递。
_ACTIVE_STATES = ("pending", "published", "failed")

_MAX_ERROR_DETAIL = 4000
_NO_RETURN_MARKER: dict = {"__no_return__": True, "note": "handler 未返回值"}


def _handler_key(index: int, handler: Any) -> str:
    return f"{index}:{getattr(handler, '__name__', repr(handler))}"[:200]


def _error_detail(exc: BaseException) -> str:
    """异常类型 + 截断堆栈；堆栈可能含凭据，按与载荷同源的文本规则遮蔽。"""
    from base.common.events.payload_contract import sanitize_text

    raw = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return sanitize_text(raw, max_bytes=_MAX_ERROR_DETAIL) or f"{type(exc).__name__}: {exc}"[:512]


@broker.task(
    task_name="taskiq:dispatch",
    queue_name="ap.events",
    retry_on_error=False,  # 重试由 Outbox 的 DB 状态机驱动，禁用中间件延迟重投
)
async def dispatch(payload: Dict[str, Any]) -> None:
    """消费一条事件消息：事务① 落凭据 → 执行 → 事务② 落终态。"""
    try:
        msg = EventMessage.model_validate(payload)
    except Exception as exc:  # 消息非法：记日志后返回（不重试，避免毒消息循环）
        logger.error(f"[taskiq:dispatch] 非法事件消息，已跳过: {exc}")
        return

    from base.common.events.event_bus import event_bus
    from base.common.events.models.event_inbox import EventInbox
    from base.common.events.models.event_record import EventRecord
    from base.common.events.payload_contract import to_jsonable
    from base.common.events.services.event_record_service import EventRecordService

    uuid = msg.event_uuid
    handlers: List[Any] = event_bus.get_handlers(msg.event_name)
    now = datetime.now(timezone.utc)

    # ---------------- 事务①：消息落库 + 状态 CAS + Inbox 凭据 ----------------
    async with in_transaction():
        record = await EventRecord.get_or_none(event_uuid=uuid)
        if record and record.status in _TERMINAL_STATUSES:
            logger.info(f"[taskiq:dispatch] 事件 {uuid} 已终态({record.status})，跳过")
            return

        claimed = await EventRecordService.transition(
            uuid,
            from_states=_ACTIVE_STATES,
            status="consuming",
            consuming_started_at=now,
        )
        if not claimed:
            logger.info(f"[taskiq:dispatch] 事件 {uuid} 状态已被并发改写，跳过本轮")
            return

        pending_keys: List[tuple] = []
        for index, handler in enumerate(handlers):
            key = _handler_key(index, handler)
            dedup_key = f"{uuid}:{key}"
            row = await EventInbox.get_or_none(dedup_key=dedup_key)
            if row is not None and row.status == "done":
                continue  # 该 handler 已成功执行，重投不再重复副作用
            if row is None:
                await EventInbox.create(
                    dedup_key=dedup_key,
                    event_uuid=uuid,
                    handler_key=key,
                    status="processing",
                    attempts=1,
                )
            else:
                await EventInbox.filter(id=row.id).update(
                    status="processing",
                    attempts=int(row.attempts or 0) + 1,
                    error_message=None,
                    error_detail=None,
                    execution_time_ms=None,
                    return_value=None,
                    finished_at=None,
                )
            pending_keys.append((key, dedup_key, handler))

    # ---------------- 事务外：执行真实 handler ----------------
    start_time = datetime.now(timezone.utc)
    outcomes: List[tuple] = []
    last_error: str | None = None
    for key, dedup_key, handler in pending_keys:
        error: str | None = None
        detail: str | None = None
        returned: Any = None
        handler_start = datetime.now(timezone.utc)
        try:
            returned = handler(msg.event_name, **msg.payload)
            if asyncio.iscoroutine(returned):
                returned = await asyncio.wait_for(
                    returned, timeout=settings.event_handler_timeout
                )
        except Exception as exc:  # 单 handler 失败隔离，不阻断其它 handler
            error = str(exc)
            last_error = error
            detail = _error_detail(exc)
            logger.error(
                f"[taskiq:dispatch] 事件 {msg.event_name} 处理器 {key} 执行失败: {exc}"
            )
        exec_ms = int(
            (datetime.now(timezone.utc) - handler_start).total_seconds() * 1000
        )
        returned_json = None
        if error is None:
            returned_json = to_jsonable(returned)
            if returned_json is None:
                returned_json = dict(_NO_RETURN_MARKER)
        outcomes.append((
            dedup_key, "done" if error is None else "failed",
            error, detail, exec_ms, returned_json,
        ))

    # ---------------- 事务②：Inbox 结果 + EventRecord 终态 ----------------
    finished_at = datetime.now(timezone.utc)
    retry_count = (int(record.retry_count or 0) if record else 0) + 1
    max_retries = _max_retries()

    async with in_transaction():
        for dedup_key, status, error, detail, exec_ms, returned_json in outcomes:
            await EventInbox.filter(dedup_key=dedup_key).update(
                status=status,
                error_message=error,
                error_detail=detail,
                execution_time_ms=exec_ms,
                return_value=returned_json,
                finished_at=finished_at,
            )

        if last_error is None:
            processing_ms = int(
                (finished_at - start_time).total_seconds() * 1000
            )
            await EventRecordService.transition(
                uuid,
                from_states=("consuming",),
                status="consumed",
                consumed_at=finished_at,
                processing_time_ms=processing_ms,
                error_message=None,
                next_retry_at=None,
            )
            return

        terminal = "failed" if retry_count < max_retries else "dead_letter"
        await EventRecordService.transition(
            uuid,
            from_states=("consuming",),
            status=terminal,
            retry_count=retry_count,
            error_message=last_error,
            next_retry_at=(
                next_retry_at_for(retry_count, finished_at)
                if retry_count < max_retries else None
            ),
        )
        if terminal == "dead_letter":
            logger.warning(
                f"[taskiq:dispatch] 事件 {uuid} 超过最大重试次数({max_retries})，"
                "进入 dead_letter（可经重放接口恢复）"
            )
            return

    # 不再上抛：failed + next_retry_at 已持久化，relay 到点补投；上抛只会触发
    # SmartRetry 的 delay label（本 broker 未配 delay_queue，必然抛错）并造成双投。
    logger.warning(
        f"[taskiq:dispatch] 事件 {uuid} handler 失败 "
        f"(retry {retry_count}/{max_retries})，等待 outbox relay 退避补投: {last_error}"
    )


def _max_retries() -> int:
    """最大重试次数：与旧链路同源（[rabbitmq] max_retries），下限 1。"""
    try:
        from base.common.setting import settings as app_settings

        return max(int(app_settings.RABBITMQ_MAX_RETRIES), 1)
    except Exception:
        return max(int(settings.retry_max), 1)
