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


class TraceRecord(BaseModel, TimestampMixin):
    verbose_name = "生产追溯"
    """生产追溯记录模型"""
    trace_code = fields.CharField(max_length=100, unique=True, description="追溯编码", index=True)
    product_batch_no = fields.CharField(max_length=100, description="成品批次号", index=True)
    material_batch_no = fields.CharField(max_length=100, description="原材料批次号", index=True)
    mo_code = fields.CharField(max_length=100, description="制造单编码", index=True)
    wo_code = fields.CharField(max_length=100, description="工单编码", index=True)
    process_code = fields.CharField(max_length=100, description="工序编码")
    operator = fields.CharField(max_length=100, description="操作员")
    equipment_code = fields.CharField(max_length=100, description="设备编码")
    work_center_code = fields.CharField(max_length=100, description="工作中心编码")
    shift_code = fields.CharField(max_length=100, description="班次编码")
    consumed_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="消耗数量")
    produced_quantity = fields.IntField(default=0, description="产出数量")

    class Meta:
        table = "mes_trace_record"

    async def to_dict(self):
        return {
            "id": self.id,
            "trace_code": self.trace_code,
            "product_batch_no": self.product_batch_no,
            "material_batch_no": self.material_batch_no,
            "mo_code": self.mo_code,
            "wo_code": self.wo_code,
            "process_code": self.process_code,
            "operator": self.operator,
            "equipment_code": self.equipment_code,
            "work_center_code": self.work_center_code,
            "shift_code": self.shift_code,
            "consumed_quantity": float(self.consumed_quantity) if self.consumed_quantity and hasattr(self.consumed_quantity, "__float__") else self.consumed_quantity,
            "produced_quantity": self.produced_quantity,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }