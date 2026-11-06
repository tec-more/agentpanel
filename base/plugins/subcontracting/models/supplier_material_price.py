from typing import Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SupplierMaterialPrice(BaseModel, TimestampMixin):
    supplier_code = fields.CharField(max_length=100, description="供应商编码", index=True)
    material_code = fields.CharField(max_length=100, description="物料编码", index=True)
    material_name = fields.CharField(max_length=255, description="物料名称")
    processing_unit_price = fields.DecimalField(max_digits=12, decimal_places=2, description="加工单价")
    currency = fields.CharField(max_length=10, default="CNY", description="币种")
    effective_date = fields.DateField(null=True, description="生效日期")
    expiry_date = fields.DateField(null=True, description="失效日期")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "supplier_material_price"

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "supplier_code": self.supplier_code,
            "material_code": self.material_code,
            "material_name": self.material_name,
            "processing_unit_price": float(self.processing_unit_price) if hasattr(self.processing_unit_price, "__float__") else self.processing_unit_price,
            "currency": self.currency,
            "effective_date": self.effective_date.strftime("%Y-%m-%d") if self.effective_date else None,
            "expiry_date": self.expiry_date.strftime("%Y-%m-%d") if self.expiry_date else None,
            "is_active": self.is_active,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }