"""Transactional Outbox relay：把消息记录投递进 ``ap.events``。

设计约束（必须诚实对待）
------------------------
1. RabbitMQ 无法参与 PG 事务，因此**只能先投递、后改状态**。若进程崩在两者
   之间，租约过期后会重投同一 event_uuid —— 由消费端 Inbox + EventRecord 终态
   幂等兜底。这是 at-least-once + 幂等 = 等效 exactly-once，不是强一致。
2. 多 worker 副本并发：用 ``locked_until`` 租约 + CAS 条件更新抢占，一行只会
   被一个 relay 取走。租约 30s，作业周期 1s（平台作业放宽下限）。
3. 投递失败不抛给上层，只释放租约 + 累加 ``dispatch_attempts``，保持原状态
   由下一轮重试；MQ 恢复后自动补投。
4. **重试唯一驱动是 DB 状态机**（2026-11-15 修订）：worker 处理失败后写
   ``failed`` + 指数退避的 ``next_retry_at``，relay 到点把 failed 重新投递。
   ``SmartRetryMiddleware`` 的 ``delay`` label 已禁用（本 broker 未配
   delay_queue，走那条路必然抛 IncorrectRoutingKeyError），不存在双重重投。
5. 悬挂态回收：``consuming`` 超时（worker 崩溃）与 ``published`` 长时间未被
   消费（投递无 publisher confirm / 消息在 MQ 侧丢失）都改回 pending 补投；
   重复补投超预算的 published 置 dead_letter，避免无限循环。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger
from tortoise.expressions import Q

RELAY_BATCH_SIZE = 100
RELAY_LEASE_SECONDS = 30
# 多 handler 串行执行，单 handler 超时 30s；留足 10 分钟避免误回收正在执行的消息
STALE_CONSUMING_SECONDS = 600
# 投递侧无 publisher confirms：published 超过 5 分钟仍未被消费则视为未确认，补投
STALE_PUBLISHED_SECONDS = 300
MAX_UNCONFIRMED_ATTEMPTS = 5
# 消费失败退避：5s / 10s / 20s / 40s ...，封顶 300s
RETRY_BASE_DELAY_SECONDS = 5
RETRY_MAX_DELAY_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def next_retry_delay(retry_count: int) -> int:
    """指数退避秒数；retry_count 从 1 开始。"""
    exponent = max(int(retry_count or 1) - 1, 0)
    return min(RETRY_BASE_DELAY_SECONDS * (2 ** exponent), RETRY_MAX_DELAY_SECONDS)


def next_retry_at_for(retry_count: int, now: datetime | None = None) -> datetime:
    """worker 写入 failed 时计算下次补投时间（relay 的唯一重投依据）。"""
    return (now or _now()) + timedelta(seconds=next_retry_delay(retry_count))


def _ready_q(now: datetime) -> Q:
    """可投递状态：pending，或 failed 且退避已到期/未设退避。"""
    return (
        Q(status="pending")
        | Q(status="failed", next_retry_at__isnull=True)
        | Q(status="failed", next_retry_at__lte=now)
    )


def _lease_q(now: datetime) -> Q:
    return Q(locked_until__isnull=True) | Q(locked_until__lte=now)


async def _claim_dispatchable(limit: int = RELAY_BATCH_SIZE) -> list:
    """CAS 抢占一批待投递/待重试记录；返回本进程独占的行快照。"""
    from base.common.events.models.event_record import EventRecord

    now = _now()
    lease_until = now + timedelta(seconds=RELAY_LEASE_SECONDS)
    candidates = await EventRecord.filter(
        _ready_q(now), _lease_q(now)
    ).order_by("published_at").limit(limit)

    claimed = []
    for row in candidates:
        updated = await EventRecord.filter(
            Q(id=row.id), _ready_q(now), _lease_q(now)
        ).update(locked_until=lease_until)
        if updated:
            claimed.append(row)
    return claimed


async def _release_lease(row, exc: Exception) -> None:
    """投递失败：释放租约、累计尝试次数，保持原状态等待下轮补投。"""
    from base.common.events.models.event_record import EventRecord

    updates = {
        "locked_until": None,
        "dispatch_attempts": int(row.dispatch_attempts or 0) + 1,
    }
    if row.status == "pending":
        # failed 行保留 worker 写下的 handler 错误，避免投递失败把排障信息覆盖掉
        updates["error_message"] = f"outbox relay: {exc}"[:1000]
    await EventRecord.filter(id=row.id, status=row.status).update(**updates)


async def relay_pending_batch(limit: int = RELAY_BATCH_SIZE) -> dict:
    """单轮投递：抢占 → dispatch.kiq → CAS 置 published。返回统计供日志/回归。

    ``failed`` 行（退避到期）与 ``pending`` 行走同一条投递通道；投递成功后按
    行原状态分别 CAS，互不覆盖。Inbox 已 done 的 handler 在重投时自动跳过。
    """
    from base.common.events.services.event_record_service import EventRecordService

    from .events import dispatch

    rows = await _claim_dispatchable(limit)
    stats = {
        "claimed": len(rows), "dispatched": 0, "failed": 0,
        "skipped": 0, "retried": 0,
    }

    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        message = {
            "event_uuid": row.event_uuid,
            "event_name": row.event_name,
            "payload": payload,
            "published_at": (
                row.published_at.isoformat() if row.published_at else ""
            ),
        }
        try:
            await dispatch.kiq(message)
        except Exception as exc:
            logger.warning(
                f"[outbox] 事件 {row.event_uuid} 投递失败，保持 {row.status} 待补投: {exc}"
            )
            await _release_lease(row, exc)
            stats["failed"] += 1
            continue

        # 先投递、后改状态：崩溃窗口由消费端幂等兜底（见模块 docstring）。
        was_retry = row.status == "failed"
        ok = await EventRecordService.transition(
            row.event_uuid,
            from_states=(row.status,),
            status="published",
            dispatched_at=_now(),
            consuming_started_at=None,
            locked_until=None,
            next_retry_at=None,
            dispatch_attempts=int(row.dispatch_attempts or 0) + 1,
            error_message=None,
        )
        if ok:
            stats["dispatched"] += 1
            if was_retry:
                stats["retried"] += 1
        else:
            # 状态已被并发操作改写（如重放），不覆盖；已投消息由 Inbox 去重。
            stats["skipped"] += 1

    return stats


async def reap_stale_consuming() -> int:
    """回收超时 consuming 记录为 pending；返回受影响行数。"""
    from base.common.events.models.event_record import EventRecord

    cutoff = _now() - timedelta(seconds=STALE_CONSUMING_SECONDS)
    return await EventRecord.filter(
        Q(status="consuming"),
        Q(consuming_started_at__lt=cutoff)
        | Q(consuming_started_at__isnull=True, published_at__lt=cutoff),
    ).update(
        status="pending",
        locked_until=None,
        dispatched_at=None,
        consuming_started_at=None,
        next_retry_at=None,
        error_message="stale consuming reaped by outbox relay",
    )


async def reap_stale_published() -> dict:
    """回收「已投递但长时间未被消费」的 published 记录。

    投递侧没有 publisher confirms，``dispatch.kiq`` 返回成功不等于 broker 已
    接收。这是 DB 侧对该窗口的兜底：超时且重投次数未超预算 → 回 pending 补投；
    超预算 → dead_letter（避免静默无限重投）。返回分类计数供日志。
    """
    from base.common.events.models.event_record import EventRecord

    cutoff = _now() - timedelta(seconds=STALE_PUBLISHED_SECONDS)
    requeued = await EventRecord.filter(
        Q(status="published"),
        Q(dispatched_at__lt=cutoff),
        Q(dispatch_attempts__lt=MAX_UNCONFIRMED_ATTEMPTS),
    ).update(
        status="pending",
        locked_until=None,
        dispatched_at=None,
        consuming_started_at=None,
        next_retry_at=None,
        error_message="unconfirmed dispatch reaped by outbox relay",
    )
    abandoned = await EventRecord.filter(
        Q(status="published"),
        Q(dispatched_at__lt=cutoff),
        Q(dispatch_attempts__gte=MAX_UNCONFIRMED_ATTEMPTS),
    ).update(
        status="dead_letter",
        error_message="unconfirmed dispatch exceeded max redelivery",
    )
    return {"requeued": requeued, "dead_letter": abandoned}
