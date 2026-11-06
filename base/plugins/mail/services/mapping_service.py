"""
事件→消息映射 Service - 配置 CRUD + 默认数据初始化
"""
from typing import Optional
from loguru import logger

from base.plugins.mail.models.model_mapping import MessageModelMapping
from base.plugins.mail.models.message_subtype import MessageSubtype
from base.plugins.mail.schemas.mapping_schema import MappingCreate, MappingUpdate, MappingListQuery


# 默认映射（与 mail_init.sql 保持一致，作为代码侧兜底）
_DEFAULT_MAPPINGS = [
    {
        "model": "purchase_order", "action": "create",
        "subtype_code": "purchase.mt_order_created",
        "name_template": "采购订单 #{record_id} 已创建",
        "body_template": "采购订单 #{record_id} 已创建",
        "notify_followers": True, "notify_creator": True,
    },
    {
        "model": "sales_order", "action": "create",
        "subtype_code": "sales.mt_order_created",
        "name_template": "销售订单 #{record_id} 已创建",
        "body_template": "销售订单 #{record_id} 已创建",
        "notify_followers": True, "notify_creator": True,
    },
    {
        "model": "approval_instance", "action": "create",
        "subtype_code": "approval.mt_instance_submitted",
        "name_template": "审批 #{record_id} 已提交",
        "body_template": "审批 #{record_id} 已提交",
        "notify_followers": False, "notify_creator": True,
    },
    {
        "model": "approval_instance", "action": "update",
        "subtype_code": "approval.mt_instance_approved",
        "condition_field": "status", "condition_value": "approved",
        "name_template": "审批 #{record_id} 已通过",
        "body_template": "审批 #{record_id} 已通过",
        "notify_followers": True, "notify_creator": True,
    },
    {
        "model": "approval_instance", "action": "update",
        "subtype_code": "approval.mt_instance_rejected",
        "condition_field": "status", "condition_value": "rejected",
        "name_template": "审批 #{record_id} 已拒绝",
        "body_template": "审批 #{record_id} 已拒绝",
        "notify_followers": True, "notify_creator": True,
    },
]


class MappingService:

    @staticmethod
    async def initialize_default_data():
        """初始化默认映射（幂等）。SQL 迁移已播种，此处代码侧兜底。"""
        for item in _DEFAULT_MAPPINGS:
            subtype = await MessageSubtype.get_or_none(code=item["subtype_code"])
            if not subtype:
                logger.warning(f"[mail] 初始化映射失败：未找到子类型 {item['subtype_code']}")
                continue
            condition_field = item.get("condition_field")
            condition_value = item.get("condition_value")
            existing = await MessageModelMapping.get_or_none(
                model=item["model"],
                action=item["action"],
                condition_field=condition_field,
                condition_value=condition_value,
            )
            if existing:
                continue
            await MessageModelMapping.create(
                model=item["model"],
                action=item["action"],
                subtype_id=subtype.id,
                condition_field=condition_field,
                condition_value=condition_value,
                name_template=item["name_template"],
                body_template=item["body_template"],
                is_active=True,
                notify_followers=item["notify_followers"],
                notify_creator=item["notify_creator"],
            )
            logger.info(f"[mail] 创建默认映射: {item['model']}.{item['action']}")

    @staticmethod
    async def list_mappings(query: MappingListQuery) -> dict:
        qs = MessageModelMapping.all()
        if query.model:
            qs = qs.filter(model=query.model)
        if query.action:
            qs = qs.filter(action=query.action)
        if query.is_active is not None:
            qs = qs.filter(is_active=query.is_active)

        total = await qs.count()
        items = await qs.order_by("model", "action").offset(
            (query.page - 1) * query.page_size
        ).limit(query.page_size)
        return {
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
            "items": [await m.to_dict(include_subtype=True) for m in items],
        }

    @staticmethod
    async def get_mapping(mapping_id: int) -> Optional[MessageModelMapping]:
        return await MessageModelMapping.get_or_none(id=mapping_id)

    @staticmethod
    async def create_mapping(data: MappingCreate) -> MessageModelMapping:
        subtype = await MessageSubtype.get_or_none(id=data.subtype_id)
        if not subtype:
            raise ValueError(f"子类型不存在: {data.subtype_id}")
        if data.action not in ("create", "update", "delete"):
            raise ValueError(f"动作非法: {data.action}")

        existing = await MessageModelMapping.get_or_none(
            model=data.model,
            action=data.action,
            condition_field=data.condition_field,
            condition_value=data.condition_value,
        )
        if existing:
            raise ValueError(
                f"映射已存在: {data.model}/{data.action}/"
                f"{data.condition_field}/{data.condition_value}"
            )
        return await MessageModelMapping.create(
            model=data.model,
            action=data.action,
            subtype_id=data.subtype_id,
            condition_field=data.condition_field,
            condition_value=data.condition_value,
            name_template=data.name_template,
            body_template=data.body_template,
            is_active=data.is_active,
            notify_followers=data.notify_followers,
            notify_creator=data.notify_creator,
        )

    @staticmethod
    async def update_mapping(mapping_id: int, data: MappingUpdate) -> Optional[MessageModelMapping]:
        m = await MessageModelMapping.get_or_none(id=mapping_id)
        if not m:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(m, k, v)
        await m.save()
        return m

    @staticmethod
    async def delete_mapping(mapping_id: int) -> bool:
        m = await MessageModelMapping.get_or_none(id=mapping_id)
        if not m:
            return False
        await m.delete()
        return True

    @staticmethod
    async def get_active_mappings(model: str, action: str):
        """事件处理器调用：获取某模型某动作的所有启用映射"""
        return await MessageModelMapping.filter(
            model=model, action=action, is_active=True
        ).all()
