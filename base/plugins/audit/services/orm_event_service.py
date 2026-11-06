
from tortoise.models import Model
from base.common.events.event_bus import event_bus
from base.common.setting import settings
from base.common.context import get_current_trace_id
from loguru import logger
from datetime import datetime, date
from decimal import Decimal
import functools


AUDIT_EXCLUDE_MODELS = [
    'AuditLog', 'InputLayerLog', 'DecisionLayerLog', 'ExecutionLayerLog',
    'OutputLayerLog', 'SystemLayerLog', 'DataChangeLog', 'LoginLog',
    'RiskAuditRecord', 'AuditReport', 'AuditConfig',
    'EventRecord', 'ReplayAuditLog',
]


def is_audit_enabled() -> bool:
    return getattr(settings, 'AUDIT_ENABLED', True)


def is_data_change_log_enabled() -> bool:
    return getattr(settings, 'AUDIT_LOG_DATA_CHANGES', True)


def is_model_excluded(model_name: str) -> bool:
    return model_name in AUDIT_EXCLUDE_MODELS


def get_instance_dict(instance) -> dict:
    data = {}
    # Use _meta.db_fields to get only actual database fields (no relations)
    for field_name in instance._meta.db_fields:
        if field_name != 'id':
            value = getattr(instance, field_name, None)
            # Convert datetime/date objects to ISO strings
            if isinstance(value, (datetime, date)):
                data[field_name] = value.isoformat()
            elif isinstance(value, Decimal):
                data[field_name] = float(value)
            else:
                data[field_name] = value
    return data


def get_changed_fields(old_data: dict, new_data: dict) -> list:
    changed = []
    all_keys = set(old_data.keys()) | set(new_data.keys())
    for key in all_keys:
        if old_data.get(key) != new_data.get(key):
            changed.append(key)
    return changed


# 存储原始的 save 方法
_original_model_save = Model.save


async def patched_model_save(self, using_db=None, **kwargs):
    """
    Monkey-patched save method that publishes audit events
    """
    model_name = self.__class__.__name__

    if is_audit_enabled() and is_data_change_log_enabled() and not is_model_excluded(model_name):
        # 判断是创建还是更新
        is_new = self.pk is None

        if not is_new:
            # 更新前获取旧数据
            try:
                old_instance = await self.__class__.get(pk=self.pk)
                old_data = get_instance_dict(old_instance)
            except Exception:
                old_data = None
        else:
            old_data = None

        # 调用原始 save 方法
        result = await _original_model_save(self, using_db, **kwargs)

        # 保存后发布事件
        table_name = getattr(self._meta, 'db_table', model_name.lower())
        record_id = str(self.pk)
        change_type = "CREATE" if is_new else "UPDATE"
        event_name = "model.created" if is_new else "model.updated"
        after_data = get_instance_dict(self)

        changed_fields = []
        if old_data:
            changed_fields = get_changed_fields(old_data, after_data)

        logger.debug(f"发布模型保存事件: {table_name}.{record_id} {change_type}")

        event_kwargs = {
            "table_name": table_name,
            "record_id": record_id,
            "change_type": change_type,
            "after_data": after_data,
            "trace_id": get_current_trace_id()
        }
        if old_data:
            event_kwargs["before_data"] = old_data
        if changed_fields:
            event_kwargs["changed_fields"] = changed_fields

        await event_bus.publish(event_name, **event_kwargs)

        return result
    else:
        # 如果审计未启用，直接调用原始 save 方法
        return await _original_model_save(self, using_db, **kwargs)


# 存储原始的 delete 方法
_original_model_delete = Model.delete


async def patched_model_delete(self, using_db=None, **kwargs):
    """
    Monkey-patched delete method that publishes audit events
    """
    model_name = self.__class__.__name__

    if is_audit_enabled() and is_data_change_log_enabled() and not is_model_excluded(model_name):
        table_name = getattr(self._meta, 'db_table', model_name.lower())
        record_id = str(self.pk)
        before_data = get_instance_dict(self)

        # 调用原始 delete 方法
        result = await _original_model_delete(self, using_db, **kwargs)

        # 发布删除事件
        logger.debug(f"发布模型删除事件: {table_name}.{record_id}")
        await event_bus.publish(
            "model.deleted",
            table_name=table_name,
            record_id=record_id,
            change_type="DELETE",
            before_data=before_data,
            trace_id=get_current_trace_id()
        )

        return result
    else:
        return await _original_model_delete(self, using_db, **kwargs)


def register_orm_audit_handlers():
    """
    注册 ORM 审计处理器（通过 monkey-patch 方式）
    """
    # 应用 monkey-patch
    Model.save = patched_model_save
    Model.delete = patched_model_delete
    logger.info("ORM审计事件监听器已注册（使用 monkey-patch 方式）")
