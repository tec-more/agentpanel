from typing import Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SubcontractingIssue(BaseModel, TimestampMixin):
    verbose_name = "委外发料"
    issue_code = fields.CharField(max_length=100, unique=True, description="发料单编码", index=True)
    sc_code = fields.CharField(max_length=100, description="委外工单编码", index=True)
    issue_type = fields.CharField(max_length=20, default="auto", description="发料类型：auto/manual")
    source_warehouse_code = fields.CharField(max_length=100, description="源仓库编码")
    source_location_code = fields.CharField(max_length=100, null=True, description="源库位编码")
    supplier_location_code = fields.CharField(max_length=100, null=True, description="供应商在途库位编码")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/canceled", index=True)
    applicant = fields.CharField(max_length=100, null=True, description="申请人")
    confirmer = fields.CharField(max_length=100, null=True, description="确认人")
    confirmed_at = fields.DatetimeField(null=True, description="确认时间")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "subcontracting_issue"

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "issue_code": self.issue_code,
            "sc_code": self.sc_code,
            "issue_type": self.issue_type,
            "source_warehouse_code": self.source_warehouse_code,
            "source_location_code": self.source_location_code,
            "supplier_location_code": self.supplier_location_code,
            "status": self.status,
            "applicant": self.applicant,
            "confirmer": self.confirmer,
            "confirmed_at": self.confirmed_at.strftime("%Y-%m-%d %H:%M:%S") if self.confirmed_at else None,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class SubcontractingIssueLine(BaseModel, TimestampMixin):
    issue_id = fields.IntField(description="发料单ID", index=True)
    material_code = fields.CharField(max_length=100, description="物料编码", index=True)
    material_name = fields.CharField(max_length=255, description="物料名称")
    required_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="需求数量")
    actual_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="实际发料数量")
    uom = fields.CharField(max_length=20, description="计量单位")
    bom_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="BOM用量")
    is_bom_material = fields.BooleanField(default=True, description="是否BOM物料")

    class Meta:
        table = "subcontracting_issue_line"

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "material_code": self.material_code,
            "material_name": self.material_name,
            "required_quantity": float(self.required_quantity) if hasattr(self.required_quantity, "__float__") else self.required_quantity,
            "actual_quantity": float(self.actual_quantity) if hasattr(self.actual_quantity, "__float__") else self.actual_quantity,
            "uom": self.uom,
            "bom_quantity": float(self.bom_quantity) if hasattr(self.bom_quantity, "__float__") else self.bom_quantity,
            "is_bom_material": self.is_bom_material,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }