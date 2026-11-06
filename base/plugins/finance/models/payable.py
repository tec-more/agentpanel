from datetime import datetime
from enum import Enum
from tortoise import fields, models
from base.common.model import BaseModel, TimestampMixin


class PayableStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    PAID = "paid"
    CANCELLED = "cancelled"


class Payable(BaseModel, TimestampMixin):
    payable_no = fields.CharField(max_length=64, unique=True, description="应付单号")
    supplier = fields.ForeignKeyField("models.Supplier", related_name="payables", on_delete=fields.SET_NULL, null=True, description="供应商")
    supplier_name = fields.CharField(max_length=128, description="供应商名称")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="应付金额")
    paid_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="已付金额")
    remaining_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="剩余金额")
    due_date = fields.DateField(description="到期日期")
    status = fields.CharEnumField(PayableStatus, max_length=20, default=PayableStatus.DRAFT, description="状态")
    source_type = fields.CharField(max_length=32, description="来源类型", default="manual")
    source_id = fields.IntField(null=True, description="来源ID")
    description = fields.TextField(null=True, description="备注")
    created_by = fields.CharField(max_length=64, description="制单人")
    confirmed_by = fields.CharField(max_length=64, null=True, description="审核人")
    
    class Meta:
        table = "finance_payables"
    
    @property
    def is_overdue(self) -> bool:
        if self.status in (PayableStatus.PAID, PayableStatus.CANCELLED):
            return False
        return datetime.now().date() > self.due_date


class PaymentStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    POSTED = "posted"
    CANCELLED = "cancelled"


class Payment(BaseModel, TimestampMixin):
    payment_no = fields.CharField(max_length=64, unique=True, description="付款单号")
    supplier = fields.ForeignKeyField("models.Supplier", related_name="payments", on_delete=fields.SET_NULL, null=True, description="供应商")
    supplier_name = fields.CharField(max_length=128, description="供应商名称")
    bank_account = fields.ForeignKeyField("models.BankAccount", related_name="payments", on_delete=fields.SET_NULL, null=True, description="银行账户")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="付款金额")
    payment_date = fields.DateField(default=datetime.now, description="付款日期")
    status = fields.CharEnumField(PaymentStatus, max_length=20, default=PaymentStatus.DRAFT, description="状态")
    payment_method = fields.CharField(max_length=32, description="付款方式", default="bank_transfer")
    description = fields.TextField(null=True, description="备注")
    created_by = fields.CharField(max_length=64, description="制单人")
    confirmed_by = fields.CharField(max_length=64, null=True, description="审核人")
    posted_by = fields.CharField(max_length=64, null=True, description="过账人")
    
    class Meta:
        table = "finance_payments"


class PayableSettlement(BaseModel, TimestampMixin):
    payable = fields.ForeignKeyField("models.Payable", related_name="settlements", on_delete=fields.CASCADE, description="应付单")
    payment = fields.ForeignKeyField("models.Payment", related_name="settlements", on_delete=fields.CASCADE, description="付款单")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="核销金额")
    settlement_date = fields.DateField(default=datetime.now, description="核销日期")
    created_by = fields.CharField(max_length=64, description="核销人")
    
    class Meta:
        table = "finance_payable_settlements"