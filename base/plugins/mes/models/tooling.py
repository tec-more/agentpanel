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


class Tooling(BaseModel, TimestampMixin):
    verbose_name = "工装夹具"
    """工装夹具模型"""
    tooling_code = fields.CharField(max_length=100, unique=True, description="工装编码", index=True)
    tooling_name = fields.CharField(max_length=255, description="工装名称")
    tooling_type = fields.CharField(max_length=20, description="工装类型：mold/fixture/cutter/gauge", index=True)
    status = fields.CharField(max_length=20, default="available", description="状态：available/in_use/maintenance/scrapped", index=True)
    life_count = fields.IntField(null=True, description="使用寿命(次数)")
    used_count = fields.IntField(default=0, description="已使用次数")
    life_hours = fields.FloatField(null=True, description="使用寿命(小时)")
    used_hours = fields.FloatField(default=0, description="已使用小时数")
    calibration_date = fields.DateField(null=True, description="上次校准日期")
    next_calibration_date = fields.DateField(null=True, description="下次校准日期")
    work_center_code = fields.CharField(max_length=100, null=True, description="所属工作中心编码")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "mes_tooling"

    async def to_dict(self):
        return {
            "id": self.id,
            "tooling_code": self.tooling_code,
            "tooling_name": self.tooling_name,
            "tooling_type": self.tooling_type,
            "status": self.status,
            "life_count": self.life_count,
            "used_count": self.used_count,
            "life_hours": self.life_hours,
            "used_hours": self.used_hours,
            "calibration_date": self.calibration_date.strftime("%Y-%m-%d") if self.calibration_date else None,
            "next_calibration_date": self.next_calibration_date.strftime("%Y-%m-%d") if self.next_calibration_date else None,
            "work_center_code": self.work_center_code,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class ToolingProcessBinding(BaseModel, TimestampMixin):
    """工装与工序关联模型"""
    tooling_code = fields.CharField(max_length=100, description="工装编码", index=True)
    process_code = fields.CharField(max_length=100, description="工序编码", index=True)

    class Meta:
        table = "mes_tooling_process_binding"

    async def to_dict(self):
        return {
            "id": self.id,
            "tooling_code": self.tooling_code,
            "process_code": self.process_code,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }