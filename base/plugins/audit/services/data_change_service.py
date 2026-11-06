import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from base.common.setting import settings
from base.plugins.audit.models.audit_log import AuditConfig, DataChangeLog
from base.plugins.audit.schemas.audit_log import DataChangeLogCreate

logger = logging.getLogger(__name__)

# 清理保留天数的最小值：低于该值会误删近期审计数据，接口与定时任务均不得低于它
MIN_RETENTION_DAYS = 30
# 数据变更模块在 audit_config 中的模块名，清理时优先读取该行的 retention_days
DATA_CHANGE_CONFIG_MODULE = "data_change"
# 最终兜底保留天数
DEFAULT_RETENTION_DAYS = 90

# 授权类表的变更记录不参与保留期清理：
# 这些记录承载「谁在何时授予/回收了什么权限、谁在何时被加入/移出组织」，
# 一旦按保留期删除即无法追溯（授权事实本身仍保留，但操作溯源永久丢失）。
# 若确需清理，必须由人工单独处理并留存外部归档。
AUTHZ_AUDIT_TABLES: Tuple[str, ...] = (
    "resource_grant",
    "customer_organization",
    "customer_organization_member",
)


def _normalize_retention(value: Any, source: str) -> Optional[int]:
    """校验保留天数：合法且不低于下限则原样返回，低于下限抬到下限并告警，非法返回 None。"""
    if not isinstance(value, int) or value <= 0:
        return None
    if value < MIN_RETENTION_DAYS:
        logger.warning(
            "%s=%s 低于最小保留天数，按 %s 天执行", source, value, MIN_RETENTION_DAYS
        )
        return MIN_RETENTION_DAYS
    return value


async def resolve_retention_days() -> int:
    """解析本次清理的保留天数。

    优先级：audit_config.retention_days > settings.AUDIT_RETAIN_DAYS > 90。
    读取失败（表不存在 / 配置缺失 / 值为空或非法）时逐级回退并记警告，绝不抛出异常，
    避免中断调用方的清理循环。
    """
    try:
        config = await AuditConfig.get_or_none(module_name=DATA_CHANGE_CONFIG_MODULE)
        configured = getattr(config, "retention_days", None) if config else None
        days = _normalize_retention(configured, "audit_config.retention_days")
        if days:
            return days
        logger.warning(
            "audit_config(%s).retention_days 缺失或非法（%r），回退到 settings.AUDIT_RETAIN_DAYS",
            DATA_CHANGE_CONFIG_MODULE,
            configured,
        )
    except Exception as e:
        logger.warning("读取 audit_config 保留天数失败，回退到 settings.AUDIT_RETAIN_DAYS: %s", e)

    days = _normalize_retention(getattr(settings, "AUDIT_RETAIN_DAYS", None), "settings.AUDIT_RETAIN_DAYS")
    if days:
        return days

    logger.warning("settings.AUDIT_RETAIN_DAYS 缺失或非法，回退到 %s 天", DEFAULT_RETENTION_DAYS)
    return DEFAULT_RETENTION_DAYS


class DataChangeService:
    model = "data_change"
    """数据变更服务"""

    @staticmethod
    async def create_log(data: DataChangeLogCreate) -> DataChangeLog:
        """创建数据变更日志"""
        if isinstance(data, dict):
            log = await DataChangeLog.create(**data)
        else:
            log = await DataChangeLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[DataChangeLog]:
        """根据ID获取数据变更日志"""
        return await DataChangeLog.get_or_none(id=log_id)

    @staticmethod
    async def get_log_list(
        page: int = 1,
        page_size: int = 20,
        table_name: Optional[str] = None,
        record_id: Optional[str] = None,
        change_type: Optional[str] = None,
        username: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Tuple[List[DataChangeLog], int]:
        """获取数据变更日志列表"""
        query = DataChangeLog.all()

        if table_name:
            query = query.filter(table_name=table_name)
        if record_id:
            query = query.filter(record_id=record_id)
        if change_type:
            query = query.filter(change_type=change_type)
        if username:
            query = query.filter(username__icontains=username)
        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)

        total = await query.count()
        offset = (page - 1) * page_size
        logs = await query.offset(offset).limit(page_size).order_by("-created_at")

        return logs, total

    @staticmethod
    async def get_changes_by_record(table_name: str, record_id: str) -> List[DataChangeLog]:
        """获取某条记录的所有变更历史"""
        logs = await DataChangeLog.filter(
            table_name=table_name,
            record_id=record_id
        ).order_by("-created_at")
        return logs

    @staticmethod
    async def delete_old_logs(
        days: int = 90,
        exclude_tables: Tuple[str, ...] = AUTHZ_AUDIT_TABLES,
    ) -> int:
        """删除旧日志（默认排除授权类表，保证授权变更可追溯）"""
        cutoff_date = datetime.now() - timedelta(days=days)
        query = DataChangeLog.filter(created_at__lt=cutoff_date)
        if exclude_tables:
            query = query.exclude(table_name__in=list(exclude_tables))
        deleted_count = await query.delete()
        return deleted_count
