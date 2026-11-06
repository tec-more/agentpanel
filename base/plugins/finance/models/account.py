from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
import random
import string


class AccountType(str, Enum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.ASSET.value: "资产",
            cls.LIABILITY.value: "负债",
            cls.EQUITY.value: "权益",
            cls.INCOME.value: "收入",
            cls.EXPENSE.value: "费用",
        }
        return labels.get(value, value)

    @classmethod
    def get_color(cls, value: str) -> str:
        colors = {
            cls.ASSET.value: "primary",
            cls.LIABILITY.value: "warning",
            cls.EQUITY.value: "success",
            cls.INCOME.value: "success",
            cls.EXPENSE.value: "danger",
        }
        return colors.get(value, "default")


class Account(BaseModel, TimestampMixin):
    verbose_name = "会计科目"
    code = fields.CharField(max_length=50, unique=True, description="科目编码")
    name = fields.CharField(max_length=255, description="科目名称")
    account_type = fields.CharEnumField(
        AccountType,
        max_length=20,
        description="科目类型"
    )
    parent = fields.ForeignKeyField(
        "models.Account",
        related_name="children",
        on_delete=fields.SET_NULL,
        null=True,
        description="上级科目"
    )
    level = fields.IntField(default=1, description="科目级别")
    is_leaf = fields.BooleanField(default=True, description="是否末级科目")
    debit_balance = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="借方余额")
    credit_balance = fields.DecimalField(max_digits=18, decimal_places=2, default=0, description="贷方余额")
    description = fields.TextField(null=True, description="科目描述")
    tax_code = fields.CharField(max_length=50, null=True, description="税务代码")
    currency_id = fields.IntField(null=True, description="币种ID")
    currency_code = fields.CharField(max_length=10, default="CNY", description="币种代码")
    reconcile = fields.BooleanField(default=False, description="是否需要对账")
    active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "finance_accounts"
        ordering = ["code"]

    async def to_dict(self) -> Dict[str, Any]:
        parent_info = None
        if self.parent:
            await self.fetch_related('parent')
            parent_info = {
                "id": self.parent.id,
                "code": self.parent.code,
                "name": self.parent.name
            }

        children = await self.children.all()
        children_list = [{"id": c.id, "code": c.code, "name": c.name} for c in children]

        balance = float(self.debit_balance) - float(self.credit_balance)

        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "account_type": self.account_type.value,
            "account_type_label": AccountType.get_label(self.account_type.value),
            "account_type_color": AccountType.get_color(self.account_type.value),
            "parent_id": self.parent_id,
            "parent": parent_info,
            "level": self.level,
            "is_leaf": self.is_leaf,
            "debit_balance": float(self.debit_balance),
            "credit_balance": float(self.credit_balance),
            "balance": balance,
            "description": self.description,
            "tax_code": self.tax_code,
            "currency_code": self.currency_code,
            "reconcile": self.reconcile,
            "active": self.active,
            "children_count": len(children_list),
            "children": children_list,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __str__(self):
        return f"{self.code} - {self.name}"


class AccountTemplate(BaseModel, TimestampMixin):
    code = fields.CharField(max_length=50, unique=True, description="模板编码")
    name = fields.CharField(max_length=255, description="模板名称")
    account_type = fields.CharEnumField(
        AccountType,
        max_length=20,
        description="科目类型"
    )
    level = fields.IntField(default=1, description="级别")
    parent_code = fields.CharField(max_length=50, null=True, description="上级模板编码")
    description = fields.TextField(null=True, description="描述")
    reconcile = fields.BooleanField(default=False, description="是否对账")

    class Meta:
        table = "finance_account_templates"
        ordering = ["code"]

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "account_type": self.account_type.value,
            "account_type_label": AccountType.get_label(self.account_type.value),
            "level": self.level,
            "parent_code": self.parent_code,
            "description": self.description,
            "reconcile": self.reconcile,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }