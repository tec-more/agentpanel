try:
    from tortoise import fields
    from tortoise.models import Model
    from base.common.model import BaseModel, TimestampMixin
except ImportError:
    from typing import Optional, Any
    from datetime import datetime

    class BaseModel:
        id = None

    class TimestampMixin:
        created_at = None
        updated_at = None

    class fields:
        @staticmethod
        def CharField(**kwargs):
            return kwargs

        @staticmethod
        def BooleanField(**kwargs):
            return kwargs

        @staticmethod
        def IntField(**kwargs):
            return kwargs

        @staticmethod
        def DatetimeField(**kwargs):
            return kwargs

        @staticmethod
        def DecimalField(**kwargs):
            return kwargs

        @staticmethod
        def TextField(**kwargs):
            return kwargs

        @staticmethod
        def JSONField(**kwargs):
            return kwargs

        @staticmethod
        def FloatField(**kwargs):
            return kwargs

        @staticmethod
        def ForeignKeyField(model_name, **kwargs):
            return kwargs

        @staticmethod
        def ManyToManyField(model_name, **kwargs):
            return kwargs

        @staticmethod
        def BigIntegerField(**kwargs):
            return kwargs


class MaterialRequisition(BaseModel, TimestampMixin):
    verbose_name = "领料单"
    """领料单模型"""
    requisition_code = fields.CharField(max_length=100, unique=True, description="领料单号", index=True)
    mo_code = fields.CharField(max_length=100, description="制造单编码", index=True)
    requisition_type = fields.CharField(max_length=20, default="auto", description="领料类型：auto/manual/by_process")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/picking/partial_done/done/canceled", index=True)
    warehouse_code = fields.CharField(max_length=100, description="领料仓库编码")
    location_code = fields.CharField(max_length=100, description="领料库位编码")
    applicant = fields.CharField(max_length=100, description="申请人")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_material_requisition"

    async def to_dict(self):
        return {
            "id": self.id,
            "requisition_code": self.requisition_code,
            "mo_code": self.mo_code,
            "requisition_type": self.requisition_type,
            "status": self.status,
            "warehouse_code": self.warehouse_code,
            "location_code": self.location_code,
            "applicant": self.applicant,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MaterialRequisitionDetail(BaseModel, TimestampMixin):
    """领料单明细模型"""
    requisition_id = fields.IntField(description="领料单ID", index=True)
    material_code = fields.CharField(max_length=100, description="物料编码", index=True)
    material_name = fields.CharField(max_length=255, description="物料名称")
    required_quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="需求数量")
    issued_quantity = fields.DecimalField(max_digits=15, decimal_places=6, default=0, description="已出库数量")
    unit = fields.CharField(max_length=20, description="计量单位")
    process_code = fields.CharField(max_length=100, null=True, description="关联工序编码")
    substitute_material_code = fields.CharField(max_length=100, null=True, description="替代物料编码")
    is_substituted = fields.BooleanField(default=False, description="是否已替代")

    class Meta:
        table = "mes_material_requisition_detail"

    async def to_dict(self):
        return {
            "id": self.id,
            "requisition_id": self.requisition_id,
            "material_code": self.material_code,
            "material_name": self.material_name,
            "required_quantity": float(self.required_quantity) if self.required_quantity and hasattr(self.required_quantity, "__float__") else self.required_quantity,
            "issued_quantity": float(self.issued_quantity) if self.issued_quantity and hasattr(self.issued_quantity, "__float__") else self.issued_quantity,
            "unit": self.unit,
            "process_code": self.process_code,
            "substitute_material_code": self.substitute_material_code,
            "is_substituted": self.is_substituted,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MaterialReturn(BaseModel, TimestampMixin):
    verbose_name = "退料单"
    """退料单模型"""
    return_code = fields.CharField(max_length=100, unique=True, description="退料单号", index=True)
    mo_code = fields.CharField(max_length=100, description="制造单编码", index=True)
    requisition_code = fields.CharField(max_length=100, description="关联领料单号")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/returning/done/canceled", index=True)
    warehouse_code = fields.CharField(max_length=100, description="退料仓库编码")
    location_code = fields.CharField(max_length=100, description="退料库位编码")
    operator = fields.CharField(max_length=100, description="操作员")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_material_return"

    async def to_dict(self):
        return {
            "id": self.id,
            "return_code": self.return_code,
            "mo_code": self.mo_code,
            "requisition_code": self.requisition_code,
            "status": self.status,
            "warehouse_code": self.warehouse_code,
            "location_code": self.location_code,
            "operator": self.operator,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class ProductionReceipt(BaseModel, TimestampMixin):
    verbose_name = "完工入库单"
    """完工入库单模型"""
    receipt_code = fields.CharField(max_length=100, unique=True, description="入库单号", index=True)
    mo_code = fields.CharField(max_length=100, description="制造单编码", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    batch_no = fields.CharField(max_length=100, unique=True, description="批次号")
    quantity = fields.IntField(description="入库数量")
    unit = fields.CharField(max_length=20, description="计量单位")
    warehouse_code = fields.CharField(max_length=100, description="入库仓库编码")
    location_code = fields.CharField(max_length=100, description="入库库位编码")
    inspection_result = fields.CharField(max_length=20, description="检验结果：qualified/concession")
    status = fields.CharField(max_length=20, default="draft", description="状态：draft/confirmed/stocking/done/canceled", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_production_receipt"

    async def to_dict(self):
        return {
            "id": self.id,
            "receipt_code": self.receipt_code,
            "mo_code": self.mo_code,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "batch_no": self.batch_no,
            "quantity": self.quantity,
            "unit": self.unit,
            "warehouse_code": self.warehouse_code,
            "location_code": self.location_code,
            "inspection_result": self.inspection_result,
            "status": self.status,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }