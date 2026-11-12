"""审计插件作业：过期数据变更日志清理（单轮，W2-3）。

原任务要求「首次执行前先 sleep，避免启动瞬间批量删除」——由调度器统一保证
（首轮先 sleep 后执行）；保留天数仍为**每轮重新解析**，后台改 audit_config
无需重启即生效。
"""


async def run() -> None:
    """清理过期数据变更日志（原 audit_cleanup_task 的单轮逻辑）。"""
    from base.plugins.audit.services.data_change_service import (
        AUTHZ_AUDIT_TABLES,
        DataChangeService,
        resolve_retention_days,
    )

    # 每轮重新解析：audit_config.retention_days > settings.AUDIT_RETAIN_DAYS > 90
    retain_days = await resolve_retention_days()
    deleted = await DataChangeService.delete_old_logs(
        days=retain_days,
        exclude_tables=AUTHZ_AUDIT_TABLES,
    )
    if deleted > 0:
        print(
            f"[定时任务] 清理过期数据变更日志 {deleted} 条"
            f"（保留 {retain_days} 天，已排除授权类表）"
        )
