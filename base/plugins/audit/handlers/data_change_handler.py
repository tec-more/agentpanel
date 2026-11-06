from base.common.events.base_handler import BaseEventHandler
from base.plugins.audit.services.data_change_service import DataChangeService
from base.common.context import current_user_id, current_username
from base.common.setting import settings
from loguru import logger


class DataChangeHandler(BaseEventHandler):
    """数据变更事件处理器"""

    enabled = True
    priority = 50

    def is_enabled(self) -> bool:
        return self.enabled and getattr(settings, 'AUDIT_ENABLED', True) and getattr(settings, 'AUDIT_LOG_DATA_CHANGES', True)

    async def handle(self, event_name: str, **kwargs):
        if not self.is_enabled():
            return

        user_id = current_user_id.get()
        username = current_username.get()
        table_name = kwargs.get('table_name')
        record_id = kwargs.get('record_id')
        change_type = kwargs.get('change_type')
        before_data = kwargs.get('before_data')
        after_data = kwargs.get('after_data')
        changed_fields = kwargs.get('changed_fields', [])
        trace_id = kwargs.get('trace_id')

        if not table_name or not record_id or not change_type:
            logger.warning("数据变更事件缺少必要参数")
            return

        try:
            await DataChangeService.create_log({
                "table_name": table_name,
                "record_id": record_id,
                "change_type": change_type,
                "before_data": before_data,
                "after_data": after_data,
                "changed_fields": changed_fields,
                "user_id": user_id,
                "username": username,
                "trace_id": trace_id,
            })
            logger.debug(f"记录数据变更日志: {table_name}.{record_id} {change_type} (trace_id={trace_id})")
        except Exception as e:
            logger.error(f"记录数据变更日志失败: {e}")