from datetime import datetime
from enum import Enum
from tortoise import fields, models
from base.common.model import BaseModel, TimestampMixin


class BillType(str, Enum):
    BANK_DRAFT = "bank_draft"
    CHECK = "check"
    BILL_OF_EXCHANGE = "bill_of_exchange"
    PROMISSORY_NOTE = "promissory_note"


class BillStatus(str, Enum):
    ISSUED = "issued"
    ACCEPTED = "accepted"
    ENDORSED = "endorsed"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Bill(BaseModel, TimestampMixin):
    bill_no = fields.CharField(max_length=64, unique=True, description="票据编号")
    bill_type = fields.CharEnumField(BillType, max_length=32, description="票据类型")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="金额")
    issue_date = fields.DateField(description="出票日期")
    due_date = fields.DateField(description="到期日期")
    issuer = fields.CharField(max_length=128, description="出票人")
    payee = fields.CharField(max_length=128, description="收款人")
    drawer_bank = fields.CharField(max_length=128, description="出票银行")
    status = fields.CharEnumField(BillStatus, max_length=20, default=BillStatus.ISSUED, description="状态")
    bank_account = fields.ForeignKeyField("models.BankAccount", related_name="bills", on_delete=fields.SET_NULL, null=True, description="关联账户")
    description = fields.TextField(null=True, description="备注")
    
    class Meta:
        table = "finance_bills"