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
        def DecimalField(**kwargs):
            return kwargs

        @staticmethod
        def TextField(**kwargs):
            return kwargs

        @staticmethod
        def JSONField(**kwargs):
            return kwargs

        @staticmethod
        def FloatField(**kwargs):
            return kwargs

        @staticmethod
        def ForeignKeyField(model_name, **kwargs):
            return kwargs

        @staticmethod
        def ManyToManyField(model_name, **kwargs):
            return kwargs

        @staticmethod
        def BigIntegerField(**kwargs):
            return kwargs


class BarcodeRecord(BaseModel, TimestampMixin):
    verbose_name = "条码记录"
    """条码记录模型"""
    barcode = fields.CharField(max_length=100, unique=True, description="条码值", index=True)
    barcode_type = fields.CharField(max_length=20, description="条码类型：work_order/material/process", index=True)
    reference_code = fields.CharField(max_length=100, description="关联业务编码", index=True)
    is_active = fields.BooleanField(default=True, description="是否有效")

    class Meta:
        table = "mes_barcode_record"

    async def to_dict(self):
        return {
            "id": self.id,
            "barcode": self.barcode,
            "barcode_type": self.barcode_type,
            "reference_code": self.reference_code,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }