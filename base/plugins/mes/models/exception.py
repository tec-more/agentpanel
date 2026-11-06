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


class ProductionException(BaseModel, TimestampMixin):
    verbose_name = "生产异常"
    """生产异常记录模型"""
    exception_code = fields.CharField(max_length=100, unique=True, description="异常编号", index=True)
    exception_type = fields.CharField(max_length=20, description="异常类型：equipment/material/quality/process/personnel", index=True)
    severity = fields.CharField(max_length=20, default="minor", description="严重程度：minor/major/critical")
    wo_code = fields.CharField(max_length=100, null=True, description="关联工单编码", index=True)
    mo_code = fields.CharField(max_length=100, null=True, description="关联制造单编码", index=True)
    work_center_code = fields.CharField(max_length=100, description="工作中心编码", index=True)
    description = fields.TextField(description="异常描述")
    reporter = fields.CharField(max_length=100, description="上报人")
    status = fields.CharField(max_length=20, default="reported", description="状态：reported/processing/resolved/closed", index=True)
    handler = fields.CharField(max_length=100, null=True, description="处理人")
    solution = fields.TextField(null=True, description="处理方案")
    resolved_at = fields.DatetimeField(null=True, description="解决时间")
    escalation_level = fields.IntField(default=0, description="升级级别：0/1/2")

    class Meta:
        table = "mes_production_exception"

    async def to_dict(self):
        return {
            "id": self.id,
            "exception_code": self.exception_code,
            "exception_type": self.exception_type,
            "severity": self.severity,
            "wo_code": self.wo_code,
            "mo_code": self.mo_code,
            "work_center_code": self.work_center_code,
            "description": self.description,
            "reporter": self.reporter,
            "status": self.status,
            "handler": self.handler,
            "solution": self.solution,
            "resolved_at": self.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if self.resolved_at else None,
            "escalation_level": self.escalation_level,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }