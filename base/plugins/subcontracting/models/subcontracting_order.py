from typing import Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SubcontractingOrder(BaseModel, TimestampMixin):
    verbose_name = "委外订单"
    sc_code = fields.CharField(max_length=100, unique=True, description="委外工单编码", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    plan_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="计划数量")
    actual_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="实际数量")
    supplier_code = fields.CharField(max_length=100, description="供应商编码", index=True)
    supplier_name = fields.CharField(max_length=255, description="供应商名称")
    process_code = fields.CharField(max_length=100, null=True, description="委外工序编码")
    process_name = fields.CharField(max_length=255, null=True, description="委外工序名称")
    processing_unit_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="加工单价")
    scrap_rate = fields.DecimalField(max_digits=5, decimal_places=4, default=0, description="损耗率")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/released/issuing/processing/partial_received/completed/closed/canceled", index=True)
    planned_start_date = fields.DatetimeField(null=True, description="计划开始日期")
    planned_end_date = fields.DatetimeField(null=True, description="计划结束日期")
    actual_start_date = fields.DatetimeField(null=True, description="实际开始日期")
    actual_end_date = fields.DatetimeField(null=True, description="实际结束日期")
    source_planned_order_code = fields.CharField(max_length=100, null=True, description="来源计划订单编码")
    source_mps_code = fields.CharField(max_length=100, null=True, description="来源MPS编码")
    total_issued_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="累计发料数量")
    total_received_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="累计收货数量")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "subcontracting_order"

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sc_code": self.sc_code,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "plan_quantity": float(self.plan_quantity) if hasattr(self.plan_quantity, "__float__") else self.plan_quantity,
            "actual_quantity": float(self.actual_quantity) if hasattr(self.actual_quantity, "__float__") else self.actual_quantity,
            "supplier_code": self.supplier_code,
            "supplier_name": self.supplier_name,
            "process_code": self.process_code,
            "process_name": self.process_name,
            "processing_unit_price": float(self.processing_unit_price) if hasattr(self.processing_unit_price, "__float__") else self.processing_unit_price,
            "scrap_rate": float(self.scrap_rate) if hasattr(self.scrap_rate, "__float__") else self.scrap_rate,
            "status": self.status,
            "planned_start_date": self.planned_start_date.strftime("%Y-%m-%d %H:%M:%S") if self.planned_start_date else None,
            "planned_end_date": self.planned_end_date.strftime("%Y-%m-%d %H:%M:%S") if self.planned_end_date else None,
            "actual_start_date": self.actual_start_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_start_date else None,
            "actual_end_date": self.actual_end_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_end_date else None,
            "source_planned_order_code": self.source_planned_order_code,
            "source_mps_code": self.source_mps_code,
            "total_issued_quantity": float(self.total_issued_quantity) if hasattr(self.total_issued_quantity, "__float__") else self.total_issued_quantity,
            "total_received_quantity": float(self.total_received_quantity) if hasattr(self.total_received_quantity, "__float__") else self.total_received_quantity,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }