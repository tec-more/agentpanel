"""
产品属性与变体数据模型
"""
try:
    from tortoise import fields
    from tortoise.models import Model
    from base.common.model import BaseModel, TimestampMixin
except ImportError:
    from typing import Optional, Any
    from datetime import datetime

    class BaseModel:
        id = None

    class TimestampMixin:
        created_at = None
        updated_at = None

    class fields:
        @staticmethod
        def CharField(**kwargs):
            return kwargs

        @staticmethod
        def BooleanField(**kwargs):
            return kwargs

        @staticmethod
        def IntField(**kwargs):
            return kwargs

        @staticmethod
        def DatetimeField(**kwargs):
            return kwargs

        @staticmethod
        def JSONField(**kwargs):
            return kwargs


class Attribute(BaseModel, TimestampMixin):
    verbose_name = "属性定义"
    """属性定义模型"""
    name = fields.CharField(max_length=50, unique=True, description="属性名称", index=True)
    code = fields.CharField(max_length=50, unique=True, description="属性编码", index=True)
    category = fields.CharField(max_length=50, default="both", description="属性类别：product/material/both")
    sort = fields.IntField(default=0, description="排序", index=True)
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "product_attribute"

    async def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "category": self.category,
            "sort": self.sort,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class AttributeValue(BaseModel, TimestampMixin):
    verbose_name = "属性值"
    """属性值模型"""
    attribute = fields.ForeignKeyField("models.Attribute", on_delete=fields.CASCADE, description="关联属性")
    value = fields.CharField(max_length=100, description="属性值")
    sort = fields.IntField(default=0, description="排序")
    product_category_id = fields.IntField(null=True, description="关联产品分类ID，null表示全品类通用")

    class Meta:
        table = "product_attribute_value"
        unique_together = ("attribute", "value", "product_category_id")

    async def to_dict(self):
        return {
            "id": self.id,
            "attribute_id": self.attribute_id,
            "attribute_name": (await self.attribute.first()).name if hasattr(self, 'attribute') else None,
            "value": self.value,
            "sort": self.sort,
            "product_category_id": self.product_category_id,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }