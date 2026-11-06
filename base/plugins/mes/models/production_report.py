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


class ProductionReport(BaseModel, TimestampMixin):
    verbose_name = "生产报工"
    """生产报工模型"""
    report_code = fields.CharField(max_length=100, unique=True, description="报工单号", index=True)
    wo_code = fields.CharField(max_length=100, description="工单编码", index=True)
    mo_code = fields.CharField(max_length=100, description="制造单编码", index=True)
    process_code = fields.CharField(max_length=100, description="工序编码", index=True)
    work_center_code = fields.CharField(max_length=100, description="工作中心编码", index=True)
    operator = fields.CharField(max_length=100, description="操作员", index=True)
    shift_code = fields.CharField(max_length=100, description="班次编码")
    equipment_code = fields.CharField(max_length=100, description="设备编码")
    batch_no = fields.CharField(max_length=100, description="批次号", index=True)
    qualified_quantity = fields.IntField(description="合格数量")
    scrap_quantity = fields.IntField(default=0, description="报废数量")
    actual_start_time = fields.DatetimeField(description="实际开始时间")
    actual_end_time = fields.DatetimeField(description="实际结束时间")
    actual_work_hours = fields.FloatField(default=0, description="实际工时(分钟)")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_production_report"

    async def to_dict(self):
        return {
            "id": self.id,
            "report_code": self.report_code,
            "wo_code": self.wo_code,
            "mo_code": self.mo_code,
            "process_code": self.process_code,
            "work_center_code": self.work_center_code,
            "operator": self.operator,
            "shift_code": self.shift_code,
            "equipment_code": self.equipment_code,
            "batch_no": self.batch_no,
            "qualified_quantity": self.qualified_quantity,
            "scrap_quantity": self.scrap_quantity,
            "actual_start_time": self.actual_start_time.strftime("%Y-%m-%d %H:%M:%S") if self.actual_start_time else None,
            "actual_end_time": self.actual_end_time.strftime("%Y-%m-%d %H:%M:%S") if self.actual_end_time else None,
            "actual_work_hours": self.actual_work_hours,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }