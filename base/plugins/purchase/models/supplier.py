from enum import Enum
from typing import Optional, Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SupplierType(str, Enum):
    MANUFACTURER = "manufacturer"
    DISTRIBUTOR = "distributor"
    RETAILER = "retailer"
    AGENT = "agent"
    SUBCONTRACTING = "subcontracting"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.MANUFACTURER.value: "生产厂家",
            cls.DISTRIBUTOR.value: "经销商",
            cls.RETAILER.value: "零售商",
            cls.AGENT.value: "代理商",
            cls.SUBCONTRACTING.value: "委外加工",
        }
        return labels.get(value, value)


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.ACTIVE.value: "启用",
            cls.INACTIVE.value: "禁用",
        }
        return labels.get(value, value)


class Supplier(BaseModel, TimestampMixin):
    supplier_code = fields.CharField(max_length=64, unique=True, description="供应商编码", index=True)
    supplier_name = fields.CharField(max_length=255, description="供应商名称")
    supplier_type = fields.CharEnumField(
        SupplierType,
        max_length=20,
        default=SupplierType.DISTRIBUTOR,
        description="供应商类型"
    )
    status = fields.CharEnumField(
        SupplierStatus,
        max_length=20,
        default=SupplierStatus.ACTIVE,
        description="状态"
    )

    contact_name = fields.CharField(max_length=100, null=True, description="联系人")
    contact_phone = fields.CharField(max_length=20, null=True, description="联系电话")
    contact_email = fields.CharField(max_length=100, null=True, description="联系邮箱")

    address = fields.TextField(null=True, description="地址")
    province = fields.CharField(max_length=50, null=True, description="省份")
    city = fields.CharField(max_length=50, null=True, description="城市")
    district = fields.CharField(max_length=50, null=True, description="区县")

    tax_id = fields.CharField(max_length=50, null=True, description="纳税人识别号")
    bank_name = fields.CharField(max_length=100, null=True, description="开户行")
    bank_account = fields.CharField(max_length=100, null=True, description="银行账号")

    credit_limit = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="信用额度")
    payment_term = fields.CharField(max_length=50, null=True, description="付款条件")
    delivery_days = fields.IntField(null=True, description="交货周期（天）")

    remark = fields.TextField(null=True, description="备注")
    is_preferred = fields.BooleanField(default=False, description="是否首选供应商")
    is_subcontracting_qualified = fields.BooleanField(default=False, description="是否具备委外加工资质")

    class Meta:
        table = "suppliers"
        ordering = ["-created_at"]

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "supplier_code": self.supplier_code,
            "supplier_name": self.supplier_name,
            "supplier_type": self.supplier_type.value,
            "supplier_type_label": SupplierType.get_label(self.supplier_type.value),
            "status": self.status.value,
            "status_label": SupplierStatus.get_label(self.status.value),
            "contact_name": self.contact_name,
            "contact_phone": self.contact_phone,
            "contact_email": self.contact_email,
            "address": self.address,
            "province": self.province,
            "city": self.city,
            "district": self.district,
            "tax_id": self.tax_id,
            "bank_name": self.bank_name,
            "bank_account": self.bank_account,
            "credit_limit": float(self.credit_limit),
            "payment_term": self.payment_term,
            "delivery_days": self.delivery_days,
            "remark": self.remark,
            "is_preferred": self.is_preferred,
            "is_subcontracting_qualified": self.is_subcontracting_qualified,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }