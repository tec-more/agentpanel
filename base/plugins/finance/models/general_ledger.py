from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class LedgerType(str, Enum):
    DAILY = "daily"
    GENERAL = "general"
    SUB = "sub"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.DAILY.value: "日记账",
            cls.GENERAL.value: "总账",
            cls.SUB.value: "明细账",
        }
        return labels.get(value, value)


class DailyJournal(BaseModel, TimestampMixin):
    journal_date = fields.DateField(default=datetime.now, description="日期")
    period = fields.CharField(max_length=10, description="会计期间")
    account = fields.ForeignKeyField(
        "models.Account",
        related_name="daily_journals",
        on_delete=fields.CASCADE,
        description="会计科目"
    )
    description = fields.TextField(null=True, description="摘要")
    reference = fields.CharField(max_length=255, null=True, description="凭证号")
    debit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="借方金额")
    credit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="贷方金额")
    balance = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="余额")
    balance_type = fields.CharField(max_length=10, default="debit", description="余额方向: debit/credit")
    journal_entry_id = fields.IntField(null=True, description="关联凭证ID")

    class Meta:
        table = "finance_daily_journals"
        ordering = ["journal_date", "account_id"]

    async def to_dict(self) -> Dict[str, Any]:
        await self.fetch_related('account')

        return {
            "id": self.id,
            "journal_date": self.journal_date.strftime("%Y-%m-%d") if self.journal_date else None,
            "period": self.period,
            "account_id": self.account_id,
            "account_code": self.account.code if self.account else None,
            "account_name": self.account.name if self.account else None,
            "description": self.description,
            "reference": self.reference,
            "debit": float(self.debit),
            "credit": float(self.credit),
            "balance": float(self.balance),
            "balance_type": self.balance_type,
            "journal_entry_id": self.journal_entry_id,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class GeneralLedger(BaseModel, TimestampMixin):
    period = fields.CharField(max_length=10, description="会计期间")
    account = fields.ForeignKeyField(
        "models.Account",
        related_name="general_ledgers",
        on_delete=fields.CASCADE,
        description="会计科目"
    )
    year = fields.IntField(description="年份")
    month = fields.IntField(description="月份")
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

    class Meta:
        table = "finance_general_ledgers"
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
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class SubLedger(BaseModel, TimestampMixin):
    period = fields.CharField(max_length=10, description="会计期间")
    account = fields.ForeignKeyField(
        "models.Account",
        related_name="sub_ledgers",
        on_delete=fields.CASCADE,
        description="总账科目"
    )
    sub_account_id = fields.IntField(null=True, description="明细科目ID")
    sub_account_name = fields.CharField(max_length=255, null=True, description="明细科目名称")
    year = fields.IntField(description="年份")
    month = fields.IntField(description="月份")
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
    partner_id = fields.IntField(null=True, description="往来单位ID")
    partner_name = fields.CharField(max_length=255, null=True, description="往来单位名称")

    class Meta:
        table = "finance_sub_ledgers"
        ordering = ["period", "account_id", "sub_account_id"]

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
            "sub_account_id": self.sub_account_id,
            "sub_account_name": self.sub_account_name,
            "partner_id": self.partner_id,
            "partner_name": self.partner_name,
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
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }