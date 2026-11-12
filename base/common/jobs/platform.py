"""平台级作业：不依赖任何插件、恒启的公共层能力（W2-3）。

任务体由 ``base/start.py`` 原样平移，只保留**单轮**业务逻辑；
while 循环、首轮 sleep、取消与异常处理统一交给 ``JobScheduler._run_loop``。
"""
from __future__ import annotations


async def quota_reconcile() -> None:
    """每分钟活跃账户配额对账落盘（Redis → PG used）+ 周期滚动。

    溯源：docs/arch/03 §3.6 事实源/对账；§5 usage 对账落盘（每分钟）。
    """
    from base.common.quota.services.quota_service import QuotaService

    result = await QuotaService.reconcile_active_accounts()
    processed = int(result.get("processed") or 0)
    skipped = int(result.get("skipped") or 0)
    if processed > 0 or skipped > 0:
        print(
            "[定时任务] 配额对账落盘完成 "
            f"batch={result.get('batch_no')} 处理 {processed} 条 / 跳过 {skipped} 条"
        )


async def quota_hold_cleanup() -> None:
    """每分钟清理悬挂预占（超 TTL 未结算的 hold 释放）。

    溯源：docs/arch/06 AR-08 quota_hold TTL + 对账任务释放悬挂预占。
    """
    from base.common.quota.services.quota_service import QuotaService

    released = await QuotaService.cleanup_stale_holds()
    if released > 0:
        print(f"[定时任务] 释放悬挂预占 {released} 个")


def install(scheduler) -> None:
    """由 ``JobScheduler.start_all()`` 调用：代码注册平台作业，不强制 manifest 化。"""
    scheduler.register_platform_job(
        "quota_reconcile",
        quota_reconcile,
        interval_seconds=60,
        description="每分钟配额对账落盘",
    )
    scheduler.register_platform_job(
        "quota_hold_cleanup",
        quota_hold_cleanup,
        interval_seconds=60,
        description="每分钟清理悬挂预占",
    )
