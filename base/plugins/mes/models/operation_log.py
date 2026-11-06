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


class OperationLog(BaseModel, TimestampMixin):
    """操作日志模型"""
    entity_type = fields.CharField(max_length=50, description="实体类型", index=True)
    entity_id = fields.IntField(description="实体ID", index=True)
    action = fields.CharField(max_length=50, description="操作类型", index=True)
    old_value = fields.JSONField(null=True, description="变更前值")
    new_value = fields.JSONField(null=True, description="变更后值")
    operator = fields.CharField(max_length=100, description="操作人")
    operated_at = fields.DatetimeField(description="操作时间")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_operation_log"

    async def to_dict(self):
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "operator": self.operator,
            "operated_at": self.operated_at.strftime("%Y-%m-%d %H:%M:%S") if self.operated_at else None,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }