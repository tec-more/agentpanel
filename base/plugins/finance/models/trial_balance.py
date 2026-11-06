from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ReportType(str, Enum):
    TRIAL_BALANCE = "trial_balance"
    BALANCE_SHEET = "balance_sheet"
    PROFIT_LOSS = "profit_loss"
    CASH_FLOW = "cash_flow"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.TRIAL_BALANCE.value: "科目余额表",
            cls.BALANCE_SHEET.value: "资产负债表",
            cls.PROFIT_LOSS.value: "利润表",
            cls.CASH_FLOW.value: "现金流量表",
        }
        return labels.get(value, value)


class TrialBalance(BaseModel, TimestampMixin):
    period = fields.CharField(max_length=10, description="会计期间")
    year = fields.IntField(description="年份")
    month = fields.IntField(description="月份")
    account = fields.ForeignKeyField(
        "models.Account",
        related_name="trial_balances",
        on_delete=fields.CASCADE,
        description="会计科目"
    )
    beginning_debit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="期初借方")
    beginning_credit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="期初贷方")
    beginning_balance = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="期初余额")
    beginning_balance_type = fields.CharField(max_length=10, default="debit", description="期初余额方向")
    debit_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="本期借方发生额")
    credit_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="本期贷方发生额")
    ending_debit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="期末借方")
    ending_credit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="期末贷方")
    ending_balance = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="期末余额")
    ending_balance_type = fields.CharField(max_length=10, default="debit", description="期末余额方向")
    is_leaf = fields.BooleanField(default=True, description="是否末级")

    class Meta:
        table = "finance_trial_balances"
        unique_together = ("period", "account_id")
        ordering = ["period", "account_id"]

    async def to_dict(self) -> Dict[str, Any]:
        await self.fetch_related('account')

        return {
            "id": self.id,
            "period": self.period,
            "year": self.year,
            "month": self.month,
            "account_id": self.account_id,
            "account_code": self.account.code if self.account else None,
            "account_name": self.account.name if self.account else None,
            "account_type": self.account.account_type.value if self.account else None,
            "account_type_label": self.account.account_type.get_label(self.account.account_type.value) if self.account else None,
            "beginning_debit": float(self.beginning_debit),
            "beginning_credit": float(self.beginning_credit),
            "beginning_balance": float(self.beginning_balance),
            "beginning_balance_type": self.beginning_balance_type,
            "debit_amount": float(self.debit_amount),
            "credit_amount": float(self.credit_amount),
            "ending_debit": float(self.ending_debit),
            "ending_credit": float(self.ending_credit),
            "ending_balance": float(self.ending_balance),
            "ending_balance_type": self.ending_balance_type,
            "is_leaf": self.is_leaf,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class FinancialReport(BaseModel, TimestampMixin):
    report_no = fields.CharField(max_length=64, unique=True, description="报表编号")
    report_type = fields.CharEnumField(
        ReportType,
        max_length=30,
        description="报表类型"
    )
    period = fields.CharField(max_length=10, description="会计期间")
    year = fields.IntField(description="年份")
    month = fields.IntField(description="月份")
    report_date = fields.DateField(default=datetime.now, description="报表日期")
    status = fields.CharField(max_length=20, default="generated", description="报表状态")
    data = fields.JSONField(null=True, description="报表数据")
    created_by = fields.CharField(max_length=50, null=True, description="生成人")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "finance_financial_reports"
        ordering = ["-report_date"]

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "report_no": self.report_no,
            "report_type": self.report_type.value,
            "report_type_label": ReportType.get_label(self.report_type.value),
            "period": self.period,
            "year": self.year,
            "month": self.month,
            "report_date": self.report_date.strftime("%Y-%m-%d") if self.report_date else None,
            "status": self.status,
            "data": self.data,
            "created_by": self.created_by,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }