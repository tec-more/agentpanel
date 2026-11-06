from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
import random
import string


class JournalType(str, Enum):
    GENERAL = "general"
    PURCHASE = "purchase"
    SALE = "sale"
    PAYMENT = "payment"
    RECEIPT = "receipt"
    INVENTORY = "inventory"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.GENERAL.value: "通用凭证",
            cls.PURCHASE.value: "采购凭证",
            cls.SALE.value: "销售凭证",
            cls.PAYMENT.value: "付款凭证",
            cls.RECEIPT.value: "收款凭证",
            cls.INVENTORY.value: "存货凭证",
        }
        return labels.get(value, value)


class JournalStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    POSTED = "posted"
    CANCELLED = "cancelled"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.DRAFT.value: "草稿",
            cls.CONFIRMED.value: "已审核",
            cls.POSTED.value: "已过账",
            cls.CANCELLED.value: "已取消",
        }
        return labels.get(value, value)

    @classmethod
    def get_color(cls, value: str) -> str:
        colors = {
            cls.DRAFT.value: "default",
            cls.CONFIRMED.value: "warning",
            cls.POSTED.value: "success",
            cls.CANCELLED.value: "danger",
        }
        return colors.get(value, "default")


def generate_journal_no() -> str:
    timestamp = datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.digits, k=6))
    return f"JV{timestamp}{random_str}"


class JournalEntry(BaseModel, TimestampMixin):
    verbose_name = "会计凭证"
    journal_no = fields.CharField(max_length=64, unique=True, description="凭证编号")
    journal_date = fields.DateField(default=datetime.now, description="凭证日期")
    journal_type = fields.CharEnumField(
        JournalType,
        max_length=20,
        default=JournalType.GENERAL,
        description="凭证类型"
    )
    status = fields.CharEnumField(
        JournalStatus,
        max_length=20,
        default=JournalStatus.DRAFT,
        description="凭证状态"
    )
    period = fields.CharField(max_length=10, description="会计期间")
    reference = fields.CharField(max_length=255, null=True, description="关联单据号")
    description = fields.TextField(null=True, description="摘要")
    total_debit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="借方合计")
    total_credit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="贷方合计")
    created_by = fields.CharField(max_length=50, null=True, description="制单人")
    confirmed_by = fields.CharField(max_length=50, null=True, description="审核人")
    confirmed_at = fields.DatetimeField(null=True, description="审核时间")
    posted_by = fields.CharField(max_length=50, null=True, description="过账人")
    posted_at = fields.DatetimeField(null=True, description="过账时间")
    cancelled_by = fields.CharField(max_length=50, null=True, description="取消人")
    cancelled_at = fields.DatetimeField(null=True, description="取消时间")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "finance_journal_entries"
        ordering = ["-journal_date", "-created_at"]

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit

    async def to_dict(self) -> Dict[str, Any]:
        lines = await self.lines.all().prefetch_related('account')
        lines_list = [await line.to_dict() for line in lines]

        return {
            "id": self.id,
            "journal_no": self.journal_no,
            "journal_date": self.journal_date.strftime("%Y-%m-%d") if self.journal_date else None,
            "journal_type": self.journal_type.value,
            "journal_type_label": JournalType.get_label(self.journal_type.value),
            "status": self.status.value,
            "status_label": JournalStatus.get_label(self.status.value),
            "status_color": JournalStatus.get_color(self.status.value),
            "period": self.period,
            "reference": self.reference,
            "description": self.description,
            "total_debit": float(self.total_debit),
            "total_credit": float(self.total_credit),
            "is_balanced": self.is_balanced,
            "created_by": self.created_by,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at.strftime("%Y-%m-%d %H:%M:%S") if self.confirmed_at else None,
            "posted_by": self.posted_by,
            "posted_at": self.posted_at.strftime("%Y-%m-%d %H:%M:%S") if self.posted_at else None,
            "cancelled_by": self.cancelled_by,
            "cancelled_at": self.cancelled_at.strftime("%Y-%m-%d %H:%M:%S") if self.cancelled_at else None,
            "remark": self.remark,
            "lines": lines_list,
            "line_count": len(lines_list),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __str__(self):
        return f"{self.journal_no} - {self.description or ''}"


class JournalLine(BaseModel, TimestampMixin):
    journal_entry = fields.ForeignKeyField(
        "models.JournalEntry",
        related_name="lines",
        on_delete=fields.CASCADE,
        description="凭证"
    )
    sequence = fields.IntField(default=1, description="行号")
    account = fields.ForeignKeyField(
        "models.Account",
        related_name="journal_lines",
        on_delete=fields.CASCADE,
        description="会计科目"
    )
    description = fields.TextField(null=True, description="摘要")
    debit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="借方金额")
    credit = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="贷方金额")
    tax_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="税额")
    tax_code = fields.CharField(max_length=50, null=True, description="税码")
    currency_code = fields.CharField(max_length=10, default="CNY", description="币种")
    exchange_rate = fields.DecimalField(max_digits=8, decimal_places=4, default=1, description="汇率")
    original_amount = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="原币金额")
    partner_id = fields.IntField(null=True, description="往来单位ID")
    partner_type = fields.CharField(max_length=20, null=True, description="往来单位类型: customer/supplier")
    analytic_account_id = fields.IntField(null=True, description="分析科目ID")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "finance_journal_lines"
        ordering = ["journal_entry_id", "sequence"]

    async def to_dict(self) -> Dict[str, Any]:
        await self.fetch_related('account')

        return {
            "id": self.id,
            "journal_entry_id": self.journal_entry_id,
            "sequence": self.sequence,
            "account_id": self.account_id,
            "account_code": self.account.code if self.account else None,
            "account_name": self.account.name if self.account else None,
            "account_type": self.account.account_type.value if self.account else None,
            "description": self.description,
            "debit": float(self.debit),
            "credit": float(self.credit),
            "tax_amount": float(self.tax_amount),
            "tax_code": self.tax_code,
            "currency_code": self.currency_code,
            "exchange_rate": float(self.exchange_rate),
            "original_amount": float(self.original_amount),
            "partner_id": self.partner_id,
            "partner_type": self.partner_type,
            "analytic_account_id": self.analytic_account_id,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }