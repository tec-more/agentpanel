from typing import Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SubcontractingSettlement(BaseModel, TimestampMixin):
    verbose_name = "委外结算"
    settlement_code = fields.CharField(max_length=100, unique=True, description="结算单编码", index=True)
    sc_code = fields.CharField(max_length=100, description="委外工单编码", index=True)
    supplier_code = fields.CharField(max_length=100, description="供应商编码", index=True)
    period_start_date = fields.DateField(null=True, description="结算期间开始日期")
    period_end_date = fields.DateField(null=True, description="结算期间结束日期")
    qualified_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="合格数量")
    concession_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="让步接收数量")
    processing_unit_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="加工单价")
    concession_discount_rate = fields.DecimalField(max_digits=5, decimal_places=4, default=1, description="让步折扣比例")
    settlement_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="结算金额")
    currency = fields.CharField(max_length=10, default="CNY", description="币种")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/submitted/approved/confirmed", index=True)
    submitter = fields.CharField(max_length=100, null=True, description="提交人")
    approver = fields.CharField(max_length=100, null=True, description="审核人")
    confirmer = fields.CharField(max_length=100, null=True, description="确认人")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "subcontracting_settlement"

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "settlement_code": self.settlement_code,
            "sc_code": self.sc_code,
            "supplier_code": self.supplier_code,
            "period_start_date": self.period_start_date.strftime("%Y-%m-%d") if self.period_start_date else None,
            "period_end_date": self.period_end_date.strftime("%Y-%m-%d") if self.period_end_date else None,
            "qualified_quantity": float(self.qualified_quantity) if hasattr(self.qualified_quantity, "__float__") else self.qualified_quantity,
            "concession_quantity": float(self.concession_quantity) if hasattr(self.concession_quantity, "__float__") else self.concession_quantity,
            "processing_unit_price": float(self.processing_unit_price) if hasattr(self.processing_unit_price, "__float__") else self.processing_unit_price,
            "concession_discount_rate": float(self.concession_discount_rate) if hasattr(self.concession_discount_rate, "__float__") else self.concession_discount_rate,
            "settlement_amount": float(self.settlement_amount) if hasattr(self.settlement_amount, "__float__") else self.settlement_amount,
            "currency": self.currency,
            "status": self.status,
            "submitter": self.submitter,
            "approver": self.approver,
            "confirmer": self.confirmer,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }