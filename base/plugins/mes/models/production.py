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


class ManufacturingOrder(BaseModel, TimestampMixin):
    """制造单模型"""
    mo_code = fields.CharField(max_length=100, unique=True, description="制造单编码", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    quantity = fields.IntField(description="计划数量")
    actual_quantity = fields.IntField(default=0, description="实际完成数量")
    status = fields.CharField(max_length=20, default="planned", description="状态：planned/released/processing/completed/canceled", index=True)
    priority = fields.CharField(max_length=20, default="normal", description="优先级：low/normal/high/urgent", index=True)
    route_code = fields.CharField(max_length=100, null=True, description="生产路线编码")
    bom_version = fields.CharField(max_length=20, null=True, description="BOM版本")
    planned_start_date = fields.DatetimeField(null=True, description="计划开始日期")
    planned_end_date = fields.DatetimeField(null=True, description="计划结束日期")
    actual_start_date = fields.DatetimeField(null=True, description="实际开始日期")
    actual_end_date = fields.DatetimeField(null=True, description="实际结束日期")
    source_mps_id = fields.IntField(null=True, description="来源MPS ID")
    source_mps_code = fields.CharField(max_length=100, null=True, description="来源MPS编号")
    source_mps_line_id = fields.IntField(null=True, description="来源MPS计划行ID")
    source_planned_order_code = fields.CharField(max_length=100, null=True, description="来源计划订单编号")
    warehouse_code = fields.CharField(max_length=100, null=True, description="入库仓库编码")
    barcode = fields.CharField(max_length=100, unique=True, null=True, description="条码")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_manufacturing_order"

    async def to_dict(self):
        return {
            "id": self.id,
            "mo_code": self.mo_code,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "actual_quantity": self.actual_quantity,
            "status": self.status,
            "priority": self.priority,
            "route_code": self.route_code,
            "bom_version": self.bom_version,
            "planned_start_date": self.planned_start_date.strftime("%Y-%m-%d %H:%M:%S") if self.planned_start_date else None,
            "planned_end_date": self.planned_end_date.strftime("%Y-%m-%d %H:%M:%S") if self.planned_end_date else None,
            "actual_start_date": self.actual_start_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_start_date else None,
            "actual_end_date": self.actual_end_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_end_date else None,
            "source_mps_id": self.source_mps_id,
            "source_mps_code": self.source_mps_code,
            "source_mps_line_id": self.source_mps_line_id,
            "source_planned_order_code": self.source_planned_order_code,
            "warehouse_code": self.warehouse_code,
            "barcode": self.barcode,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class WorkOrder(BaseModel, TimestampMixin):
    verbose_name = "工单"
    """工单模型"""
    wo_code = fields.CharField(max_length=100, unique=True, description="工单编码", index=True)
    mo_code = fields.CharField(max_length=100, description="制造单编码", index=True)
    mo_name = fields.CharField(max_length=255, null=True, description="制造单名称")
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    process_code = fields.CharField(max_length=100, description="工序编码", index=True)
    process_name = fields.CharField(max_length=255, description="工序名称")
    work_center_code = fields.CharField(max_length=100, null=True, description="工作中心编码", index=True)
    work_center_name = fields.CharField(max_length=255, null=True, description="工作中心名称")
    quantity = fields.IntField(description="计划数量")
    actual_quantity = fields.IntField(default=0, description="实际完成数量")
    scrap_quantity = fields.IntField(default=0, description="报废数量")
    status = fields.CharField(max_length=20, default="pending", description="状态：pending/released/processing/suspended/completed/closed", index=True)
    operator = fields.CharField(max_length=100, null=True, description="操作员")
    equipment_code = fields.CharField(max_length=100, null=True, description="设备编码")
    shift_code = fields.CharField(max_length=100, null=True, description="班次编码")
    batch_no = fields.CharField(max_length=100, null=True, description="批次号")
    barcode = fields.CharField(max_length=100, unique=True, null=True, description="条码")
    suspend_reason = fields.CharField(max_length=50, null=True, description="暂停原因：equipment/quality/exception")
    suspend_source = fields.CharField(max_length=100, null=True, description="暂停来源编码")
    suspended_at = fields.DatetimeField(null=True, description="暂停时间")
    planned_start_date = fields.DatetimeField(null=True, description="计划开始日期")
    planned_end_date = fields.DatetimeField(null=True, description="计划结束日期")
    actual_start_date = fields.DatetimeField(null=True, description="实际开始日期")
    actual_end_date = fields.DatetimeField(null=True, description="实际结束日期")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_work_order"

    async def to_dict(self):
        return {
            "id": self.id,
            "wo_code": self.wo_code,
            "mo_code": self.mo_code,
            "mo_name": self.mo_name,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "process_code": self.process_code,
            "process_name": self.process_name,
            "work_center_code": self.work_center_code,
            "work_center_name": self.work_center_name,
            "quantity": self.quantity,
            "actual_quantity": self.actual_quantity,
            "scrap_quantity": self.scrap_quantity,
            "status": self.status,
            "operator": self.operator,
            "equipment_code": self.equipment_code,
            "shift_code": self.shift_code,
            "batch_no": self.batch_no,
            "barcode": self.barcode,
            "suspend_reason": self.suspend_reason,
            "suspend_source": self.suspend_source,
            "suspended_at": self.suspended_at.strftime("%Y-%m-%d %H:%M:%S") if self.suspended_at else None,
            "planned_start_date": self.planned_start_date.strftime("%Y-%m-%d %H:%M:%S") if self.planned_start_date else None,
            "planned_end_date": self.planned_end_date.strftime("%Y-%m-%d %H:%M:%S") if self.planned_end_date else None,
            "actual_start_date": self.actual_start_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_start_date else None,
            "actual_end_date": self.actual_end_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_end_date else None,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }