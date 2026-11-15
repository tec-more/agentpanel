"""平台级作业：不依赖任何插件、恒启的公共层能力（M2 迁自 base/common/jobs/platform.py）。

这里是**系统级作业的唯一发现点**：``base.common.taskiq_app.discovery`` 固定
import 本模块触发 ``@broker.task`` 注册，再从 ``ap_schedule`` 标签读出调度周期。
周期不再由 ``reconcile.py`` 硬编码，新增平台作业只需在本文件加一个带声明的
``@broker.task``，beat / worker 无需改动。

只保留**单轮**业务逻辑；调度行的写入由 taskiq-beat 的 reconciler 完成，
job_id 前缀 ``platform:``（owner 恒为 platform，不受插件启停门控影响）。
"""
from __future__ import annotations

from loguru import logger

from base.common.taskiq_app.broker import broker


@broker.task(
    task_name="platform:quota_reconcile",
    queue_name="ap.jobs",
    ap_schedule=60,
    ap_description="每分钟活跃账户配额对账落盘（Redis → PG used）+ 周期滚动",
)
async def quota_reconcile() -> None:
    """每分钟活跃账户配额对账落盘（Redis → PG used）+ 周期滚动。

    溯源：docs/arch/03 §3.6 事实源/对账；§5 usage 对账落盘（每分钟）。
    """
    from base.common.quota.services.quota_service import QuotaService

    result = await QuotaService.reconcile_active_accounts()
    processed = int(result.get("processed") or 0)
    skipped = int(result.get("skipped") or 0)
    if processed > 0 or skipped > 0:
        logger.info(
            "[平台作业] 配额对账落盘完成 "
            f"batch={result.get('batch_no')} 处理 {processed} 条 / 跳过 {skipped} 条"
        )


@broker.task(
    task_name="platform:quota_hold_cleanup",
    queue_name="ap.jobs",
    ap_schedule=60,
    ap_description="每分钟清理悬挂预占（超 TTL 未结算的 hold 释放）",
)
async def quota_hold_cleanup() -> None:
    """每分钟清理悬挂预占（超 TTL 未结算的 hold 释放）。

    溯源：docs/arch/06 AR-08 quota_hold TTL + 对账任务释放悬挂预占。
    """
    from base.common.quota.services.quota_service import QuotaService

    released = await QuotaService.cleanup_stale_holds()
    if released > 0:
        logger.info(f"[平台作业] 释放悬挂预占 {released} 个")


@broker.task(
    task_name="platform:outbox_relay",
    queue_name="ap.jobs",
    ap_schedule=1,
    ap_description="Outbox：投递 pending 与退避到期的 failed 消息进 ap.events",
)
async def outbox_relay() -> None:
    """秒级轮询事务性发件箱：投递唯一通道，也是失败事件唯一的重试驱动。

    ap_schedule=1 依赖 discovery.PLATFORM_MIN_JOB_INTERVAL（平台作业下限 1s，
    插件作业仍 ≥30s）。投递失败保持原状态，MQ 恢复后自动补投；worker 失败后
    写入的 failed + next_retry_at 到点由本作业重新投递（DB 状态机驱动退避）。
    """
    from base.common.taskiq_app.outbox import relay_pending_batch

    stats = await relay_pending_batch()
    if stats["dispatched"] or stats["failed"]:
        logger.info(
            f"[outbox] 本轮投递 claimed={stats['claimed']} "
            f"dispatched={stats['dispatched']} retried={stats['retried']} "
            f"failed={stats['failed']} skipped={stats['skipped']}"
        )


@broker.task(
    task_name="platform:stale_consuming_reap",
    queue_name="ap.jobs",
    ap_schedule=30,
    ap_description="回收超时 consuming 与未确认 published 消息，交 relay 补投",
)
async def stale_consuming_reap() -> None:
    """两类悬挂态回收（Inbox 已 done 的 handler 会跳过重复执行）：

    - ``consuming`` 超时：worker 崩溃，事务②未提交；
    - ``published`` 超时：投递侧无 publisher confirms，MQ 侧可能没收到。
    """
    from base.common.taskiq_app.outbox import (
        reap_stale_consuming,
        reap_stale_published,
    )

    reset = await reap_stale_consuming()
    unconfirmed = await reap_stale_published()
    if reset:
        logger.warning(f"[outbox] 回收 {reset} 条超时 consuming 消息为 pending")
    if unconfirmed["requeued"] or unconfirmed["dead_letter"]:
        logger.warning(
            f"[outbox] 未确认投递回收 requeued={unconfirmed['requeued']} "
            f"dead_letter={unconfirmed['dead_letter']}"
        )
