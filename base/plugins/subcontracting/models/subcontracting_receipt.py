from typing import Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SubcontractingReceipt(BaseModel, TimestampMixin):
    verbose_name = "委外收货"
    receipt_code = fields.CharField(max_length=100, unique=True, description="收货单编码", index=True)
    sc_code = fields.CharField(max_length=100, description="委外工单编码", index=True)
    supplier_code = fields.CharField(max_length=100, description="供应商编码")
    receipt_warehouse_code = fields.CharField(max_length=100, description="收货仓库编码")
    receipt_location_code = fields.CharField(max_length=100, null=True, description="收货库位编码")
    inspection_result = fields.CharField(max_length=20, null=True, description="质检结果：qualified/unqualified/concession")
    inspector = fields.CharField(max_length=100, null=True, description="质检员")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/canceled", index=True)
    receiver = fields.CharField(max_length=100, null=True, description="收货人")
    confirmed_at = fields.DatetimeField(null=True, description="确认时间")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "subcontracting_receipt"

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "receipt_code": self.receipt_code,
            "sc_code": self.sc_code,
            "supplier_code": self.supplier_code,
            "receipt_warehouse_code": self.receipt_warehouse_code,
            "receipt_location_code": self.receipt_location_code,
            "inspection_result": self.inspection_result,
            "inspector": self.inspector,
            "status": self.status,
            "receiver": self.receiver,
            "confirmed_at": self.confirmed_at.strftime("%Y-%m-%d %H:%M:%S") if self.confirmed_at else None,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class SubcontractingReceiptLine(BaseModel, TimestampMixin):
    receipt_id = fields.IntField(description="收货单ID", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码")
    product_name = fields.CharField(max_length=255, description="产品名称")
    receipt_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="收货数量")
    qualified_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="合格数量")
    unqualified_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="不合格数量")
    concession_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="让步接收数量")
    uom = fields.CharField(max_length=20, description="计量单位")
    batch_no = fields.CharField(max_length=100, null=True, description="批次号")

    class Meta:
        table = "subcontracting_receipt_line"

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "receipt_id": self.receipt_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "receipt_quantity": float(self.receipt_quantity) if hasattr(self.receipt_quantity, "__float__") else self.receipt_quantity,
            "qualified_quantity": float(self.qualified_quantity) if hasattr(self.qualified_quantity, "__float__") else self.qualified_quantity,
            "unqualified_quantity": float(self.unqualified_quantity) if hasattr(self.unqualified_quantity, "__float__") else self.unqualified_quantity,
            "concession_quantity": float(self.concession_quantity) if hasattr(self.concession_quantity, "__float__") else self.concession_quantity,
            "uom": self.uom,
            "batch_no": self.batch_no,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }