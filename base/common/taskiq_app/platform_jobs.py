"""平台级作业：不依赖任何插件、恒启的公共层能力（M2 迁自 base/common/jobs/platform.py）。

只保留**单轮**业务逻辑；周期与触发由 taskiq-beat 的 reconciler 写入调度行
（reconcile.py 平台作业段，job_id 前缀 ``platform:``），worker 进程执行。
"""
from __future__ import annotations

from loguru import logger

from base.common.taskiq_app.broker import broker


@broker.task(task_name="platform:quota_reconcile", queue_name="ap.jobs")
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


@broker.task(task_name="platform:quota_hold_cleanup", queue_name="ap.jobs")
async def quota_hold_cleanup() -> None:
    """每分钟清理悬挂预占（超 TTL 未结算的 hold 释放）。

    溯源：docs/arch/06 AR-08 quota_hold TTL + 对账任务释放悬挂预占。
    """
    from base.common.quota.services.quota_service import QuotaService

    released = await QuotaService.cleanup_stale_holds()
    if released > 0:
        logger.info(f"[平台作业] 释放悬挂预占 {released} 个")
