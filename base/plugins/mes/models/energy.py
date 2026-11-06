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


class EnergyRecord(BaseModel, TimestampMixin):
    verbose_name = "能耗记录"
    """能耗记录模型"""
    equipment_code = fields.CharField(max_length=100, description="设备编码", index=True)
    energy_type = fields.CharField(max_length=20, description="能耗类型：electric/water/gas", index=True)
    consumption_value = fields.DecimalField(max_digits=15, decimal_places=6, description="消耗值")
    unit = fields.CharField(max_length=20, description="计量单位(kWh/m³)")
    record_time = fields.DatetimeField(description="记录时间", index=True)
    work_center_code = fields.CharField(max_length=100, description="工作中心编码", index=True)
    shift_code = fields.CharField(max_length=100, null=True, description="班次编码")

    class Meta:
        table = "mes_energy_record"

    async def to_dict(self):
        return {
            "id": self.id,
            "equipment_code": self.equipment_code,
            "energy_type": self.energy_type,
            "consumption_value": float(self.consumption_value) if self.consumption_value and hasattr(self.consumption_value, "__float__") else self.consumption_value,
            "unit": self.unit,
            "record_time": self.record_time.strftime("%Y-%m-%d %H:%M:%S") if self.record_time else None,
            "work_center_code": self.work_center_code,
            "shift_code": self.shift_code,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }