"""
消息子类型 Service
"""
from typing import Optional, List
from loguru import logger

from base.plugins.mail.models.message_subtype import MessageSubtype
from base.plugins.mail.schemas.subtype_schema import SubtypeCreate, SubtypeUpdate, SubtypeListQuery


# 默认子类型（系统预设，与 mail_init.sql 保持一致）
_DEFAULT_SUBTYPES = [
    {"name": "评论", "code": "mt_comment", "description": "用户评论/日志",
     "model": None, "default": True, "internal": False, "sequence": 10},
    {"name": "系统通知", "code": "mt_notification", "description": "系统自动通知",
     "model": None, "default": False, "internal": False, "sequence": 20},
    {"name": "采购订单已创建", "code": "purchase.mt_order_created",
     "description": "采购订单创建时通知", "model": "purchase_order",
     "default": False, "internal": False, "sequence": 30},
    {"name": "销售订单已创建", "code": "sales.mt_order_created",
     "description": "销售订单创建时通知", "model": "sales_order",
     "default": False, "internal": False, "sequence": 40},
    {"name": "审批已提交", "code": "approval.mt_instance_submitted",
     "description": "审批实例提交", "model": "approval_instance",
     "default": False, "internal": False, "sequence": 50},
    {"name": "审批已通过", "code": "approval.mt_instance_approved",
     "description": "审批实例通过", "model": "approval_instance",
     "default": False, "internal": False, "sequence": 51},
    {"name": "审批已拒绝", "code": "approval.mt_instance_rejected",
     "description": "审批实例拒绝", "model": "approval_instance",
     "default": False, "internal": False, "sequence": 52},
]


class SubtypeService:

    @staticmethod
    async def initialize_default_data():
        """初始化默认子类型（幂等：SQL 迁移已播种，此处兜底）"""
        for item in _DEFAULT_SUBTYPES:
            existing = await MessageSubtype.get_or_none(code=item["code"])
            if existing:
                continue
            await MessageSubtype.create(
                name=item["name"], code=item["code"], description=item["description"],
                model=item["model"], default=item["default"], internal=item["internal"],
                sequence=item["sequence"], is_active=True, is_system=True,
            )
            logger.info(f"[mail] 创建默认子类型: {item['code']}")

    @staticmethod
    async def get_subtype(subtype_id: int) -> Optional[MessageSubtype]:
        return await MessageSubtype.get_or_none(id=subtype_id)

    @staticmethod
    async def get_by_code(code: str) -> Optional[MessageSubtype]:
        return await MessageSubtype.get_or_none(code=code)

    @staticmethod
    async def get_default_subtype() -> Optional[MessageSubtype]:
        """获取评论默认子类型（mt_comment）"""
        return await MessageSubtype.get_or_none(code="mt_comment")

    @staticmethod
    async def list_subtypes(query: SubtypeListQuery) -> dict:
        qs = MessageSubtype.all()
        if query.model is not None:
            qs = qs.filter(model=query.model)
        if query.is_active is not None:
            qs = qs.filter(is_active=query.is_active)
        if query.keyword:
            qs = qs.filter(name__icontains=query.keyword) | qs.filter(code__icontains=query.keyword)

        total = await qs.count()
        items = await qs.order_by("sequence", "id").offset(
            (query.page - 1) * query.page_size
        ).limit(query.page_size)
        return {
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
            "items": [await s.to_dict() for s in items],
        }

    @staticmethod
    async def create_subtype(data: SubtypeCreate) -> MessageSubtype:
        existing = await MessageSubtype.get_or_none(code=data.code)
        if existing:
            raise ValueError(f"子类型编码已存在: {data.code}")
        return await MessageSubtype.create(
            name=data.name, code=data.code, description=data.description,
            model=data.model, default=data.default, internal=data.internal,
            sequence=data.sequence, is_active=data.is_active, is_system=False,
        )

    @staticmethod
    async def update_subtype(subtype_id: int, data: SubtypeUpdate) -> Optional[MessageSubtype]:
        subtype = await MessageSubtype.get_or_none(id=subtype_id)
        if not subtype:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(subtype, k, v)
        await subtype.save()
        return subtype

    @staticmethod
    async def delete_subtype(subtype_id: int) -> bool:
        subtype = await MessageSubtype.get_or_none(id=subtype_id)
        if not subtype:
            return False
        if subtype.is_system:
            raise ValueError("系统预设子类型不可删除")
        await subtype.delete()
        return True
