from datetime import datetime
from enum import Enum
from tortoise import fields, models
from base.common.model import BaseModel, TimestampMixin


class ExpenseType(str, Enum):
    TRAVEL = "travel"
    ENTERTAINMENT = "entertainment"
    OFFICE = "office"
    COMMUNICATION = "communication"
    TRANSPORTATION = "transportation"
    OTHER = "other"


class ExpenseStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class ExpenseApply(BaseModel, TimestampMixin):
    apply_no = fields.CharField(max_length=64, unique=True, description="申请单号")
    applicant = fields.ForeignKeyField("models.User", related_name="expense_applies", on_delete=fields.SET_NULL, null=True, description="申请人")
    applicant_name = fields.CharField(max_length=64, description="申请人姓名")
    department = fields.ForeignKeyField("models.Department", related_name="expense_applies", on_delete=fields.SET_NULL, null=True, description="部门")
    expense_type = fields.CharEnumField(ExpenseType, max_length=32, description="费用类型")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="申请金额")
    apply_date = fields.DateField(default=datetime.now, description="申请日期")
    status = fields.CharEnumField(ExpenseStatus, max_length=20, default=ExpenseStatus.PENDING, description="状态")
    description = fields.TextField(null=True, description="申请事由")
    account = fields.ForeignKeyField("models.Account", related_name="expense_applies", on_delete=fields.SET_NULL, null=True, description="会计科目")
    approved_by = fields.CharField(max_length=64, null=True, description="审批人")
    approved_date = fields.DateField(null=True, description="审批日期")
    
    class Meta:
        table = "finance_expense_applies"


class ExpenseReport(BaseModel, TimestampMixin):
    report_no = fields.CharField(max_length=64, unique=True, description="报销单号")
    apply = fields.ForeignKeyField("models.ExpenseApply", related_name="reports", on_delete=fields.CASCADE, description="关联申请")
    applicant = fields.ForeignKeyField("models.User", related_name="expense_reports", on_delete=fields.SET_NULL, null=True, description="报销人")
    applicant_name = fields.CharField(max_length=64, description="报销人姓名")
    bank_account = fields.ForeignKeyField("models.BankAccount", related_name="expense_reports", on_delete=fields.SET_NULL, null=True, description="收款账户")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="报销金额")
    report_date = fields.DateField(default=datetime.now, description="报销日期")
    status = fields.CharField(max_length=20, default="pending", description="状态")
    journal_entry = fields.ForeignKeyField("models.JournalEntry", related_name="expense_reports", on_delete=fields.SET_NULL, null=True, description="关联凭证")
    posted_by = fields.CharField(max_length=64, null=True, description="过账人")
    
    class Meta:
        table = "finance_expense_reports"


class ExpenseItem(BaseModel, TimestampMixin):
    report = fields.ForeignKeyField("models.ExpenseReport", related_name="items", on_delete=fields.CASCADE, description="报销单")
    expense_date = fields.DateField(description="费用日期")
    description = fields.CharField(max_length=256, description="费用说明")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="金额")
    account = fields.ForeignKeyField("models.Account", related_name="expense_items", on_delete=fields.SET_NULL, null=True, description="会计科目")
    
    class Meta:
        table = "finance_expense_items"