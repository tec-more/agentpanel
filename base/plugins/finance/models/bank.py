from datetime import datetime
from tortoise import fields, models
from base.common.model import BaseModel, TimestampMixin


class BankAccount(BaseModel, TimestampMixin):
    account_name = fields.CharField(max_length=128, description="账户名称")
    bank_name = fields.CharField(max_length=128, description="银行名称")
    account_no = fields.CharField(max_length=64, unique=True, description="银行账号")
    currency = fields.CharField(max_length=16, default="CNY", description="币种")
    balance = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="账户余额")
    is_active = fields.BooleanField(default=True, description="是否启用")
    description = fields.TextField(null=True, description="备注")
    
    class Meta:
        table = "finance_bank_accounts"


class CashFlowRecord(BaseModel, TimestampMixin):
    bank_account = fields.ForeignKeyField("models.BankAccount", related_name="cash_flows", on_delete=fields.CASCADE, description="银行账户")
    flow_date = fields.DateField(default=datetime.now, description="流水日期")
    amount = fields.DecimalField(max_digits=18, decimal_places=2, description="金额")
    flow_type = fields.CharField(max_length=32, description="流水类型")
    balance = fields.DecimalField(max_digits=18, decimal_places=2, description="余额")
    description = fields.TextField(null=True, description="摘要")
    reference_no = fields.CharField(max_length=64, null=True, description="凭证号")
    
    class Meta:
        table = "finance_cash_flow_records"


class CashPlan(BaseModel, TimestampMixin):
    plan_no = fields.CharField(max_length=64, unique=True, description="计划编号")
    period = fields.CharField(max_length=10, description="计划期间")
    inflow_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="预计流入")
    outflow_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="预计流出")
    net_amount = fields.DecimalField(max_digits=18, decimal_places=2, description="净流量")
    status = fields.CharField(max_length=20, default="draft", description="状态")
    description = fields.TextField(null=True, description="备注")
    created_by = fields.CharField(max_length=64, description="编制人")
    
    class Meta:
        table = "finance_cash_plans"