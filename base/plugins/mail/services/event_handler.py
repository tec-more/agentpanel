"""
消息事件处理器 - 订阅 audit 的 model.* 事件，按映射配置自动产生系统消息

订阅的事件（由 base/plugins/audit/services/orm_event_service.py 发布）：
- model.created: kwargs = {table_name, record_id, change_type='CREATE',
                            after_data, trace_id}
- model.updated: kwargs = {table_name, record_id, change_type='UPDATE',
                            after_data, before_data, changed_fields, trace_id}
- model.deleted: kwargs = {table_name, record_id, change_type='DELETE',
                            before_data, trace_id}
"""
from typing import Optional, List
from loguru import logger

from base.common.events.event_bus import event_bus
from base.plugins.mail.services.mapping_service import MappingService
from base.plugins.mail.services.message_service import MessageService
from base.plugins.mail.services.template_service import render_template


# 系统消息作者ID（0 表示系统）
SYSTEM_AUTHOR_ID = 0

# 邮件模块自己的表，避免自递归（mail_message / mail_notification 等变更不再触发 mail 自身消息）
_MAIL_OWN_TABLES = {
    "mail_message", "mail_message_subtype",
    "mail_follower", "mail_notification", "mail_model_mapping",
}


class MailEventHandler:
    """订阅 model.* 事件，按 MessageModelMapping 配置自动落库系统消息。"""

    def __init__(self):
        self._is_registered = False
        # 保存实例方法引用，便于精确 unsubscribe
        self._handle_created = self._handle_created_impl
        self._handle_updated = self._handle_updated_impl
        self._handle_deleted = self._handle_deleted_impl

    # ==================== 事件处理 ====================

    async def _handle_created_impl(self, event_name: str, **kwargs):
        table_name = kwargs.get("table_name")
        record_id = kwargs.get("record_id")
        after_data = kwargs.get("after_data") or {}

        if not table_name or not record_id:
            return
        if table_name in _MAIL_OWN_TABLES:
            return

        try:
            mappings = await MappingService.get_active_mappings(table_name, "create")
            for mapping in mappings:
                # create 动作忽略 condition_field（不适用于 create）
                await self._post_from_mapping(mapping, record_id, after_data, before_data=None)
        except Exception as e:
            logger.error(f"[mail] 处理 model.created 事件失败: {table_name}.{record_id} -> {e}")

    async def _handle_updated_impl(self, event_name: str, **kwargs):
        table_name = kwargs.get("table_name")
        record_id = kwargs.get("record_id")
        after_data = kwargs.get("after_data") or {}
        before_data = kwargs.get("before_data") or {}
        changed_fields = kwargs.get("changed_fields") or []

        if not table_name or not record_id:
            return
        if table_name in _MAIL_OWN_TABLES:
            return

        try:
            mappings = await MappingService.get_active_mappings(table_name, "update")
            for mapping in mappings:
                if not self._match_update_condition(mapping, changed_fields, after_data):
                    continue
                await self._post_from_mapping(mapping, record_id, after_data, before_data)
        except Exception as e:
            logger.error(f"[mail] 处理 model.updated 事件失败: {table_name}.{record_id} -> {e}")

    async def _handle_deleted_impl(self, event_name: str, **kwargs):
        table_name = kwargs.get("table_name")
        record_id = kwargs.get("record_id")
        before_data = kwargs.get("before_data") or {}

        if not table_name or not record_id:
            return
        if table_name in _MAIL_OWN_TABLES:
            return

        try:
            mappings = await MappingService.get_active_mappings(table_name, "delete")
            for mapping in mappings:
                await self._post_from_mapping(
                    mapping, record_id,
                    after_data=before_data,  # delete 时只有 before_data
                    before_data=before_data,
                )
        except Exception as e:
            logger.error(f"[mail] 处理 model.deleted 事件失败: {table_name}.{record_id} -> {e}")

    # ==================== 条件匹配与消息生成 ====================

    @staticmethod
    def _match_update_condition(mapping, changed_fields: List[str], after_data: dict) -> bool:
        """update 映射的条件过滤。

        - condition_field 为空 → 任意 update 都触发
        - condition_field 非空 → 要求该字段在 changed_fields 内
        - condition_value 非空 → 进一步要求 after_data[condition_field] == condition_value
        """
        if not mapping.condition_field:
            return True
        if mapping.condition_field not in changed_fields:
            return False
        if mapping.condition_value is None:
            return True
        actual = after_data.get(mapping.condition_field)
        return str(actual) == str(mapping.condition_value)

    @staticmethod
    async def _post_from_mapping(mapping, record_id, after_data: dict,
                                  before_data: Optional[dict]):
        """根据映射渲染模板并发消息。"""
        subject = render_template(
            mapping.name_template, record_id=record_id,
            data=after_data, before_data=before_data,
        )
        body = render_template(
            mapping.body_template, record_id=record_id,
            data=after_data, before_data=before_data,
        )
        # 模板为空时退化为子类型名称
        if not subject:
            subject = getattr(mapping, "_subtype_name_cache", None) or f"#{record_id}"
        if not body:
            body = subject

        await MessageService.post_message(
            model=mapping.model,
            res_id=int(record_id) if record_id is not None else None,
            body=body,
            author_id=SYSTEM_AUTHOR_ID,
            subtype_id=mapping.subtype_id,
            message_type="notification",
            subject=subject,
            notify_followers=mapping.notify_followers,
            notify_creator=mapping.notify_creator,
            record_data=after_data,
        )


# ==================== 全局注册/注销 ====================

# 全局单例（保持引用一致以便 unsubscribe）
_mail_event_handler: Optional[MailEventHandler] = None


def register_mail_event_handlers():
    """注册 mail 事件订阅（幂等：重复调用不会重复订阅）。"""
    global _mail_event_handler
    if _mail_event_handler is not None and _mail_event_handler._is_registered:
        logger.debug("[mail] 事件处理器已注册，跳过")
        return

    if _mail_event_handler is None:
        _mail_event_handler = MailEventHandler()

    event_bus.subscribe("model.created", _mail_event_handler._handle_created)
    event_bus.subscribe("model.updated", _mail_event_handler._handle_updated)
    event_bus.subscribe("model.deleted", _mail_event_handler._handle_deleted)
    _mail_event_handler._is_registered = True
    logger.info("[mail] 事件处理器已注册（订阅 model.created/updated/deleted）")


def unregister_mail_event_handlers():
    """注销 mail 事件订阅。"""
    global _mail_event_handler
    if _mail_event_handler is None or not _mail_event_handler._is_registered:
        return

    event_bus.unsubscribe("model.created", _mail_event_handler._handle_created)
    event_bus.unsubscribe("model.updated", _mail_event_handler._handle_updated)
    event_bus.unsubscribe("model.deleted", _mail_event_handler._handle_deleted)
    _mail_event_handler._is_registered = False
    logger.info("[mail] 事件处理器已注销")
