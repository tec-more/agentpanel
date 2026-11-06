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


class QualityInspection(BaseModel, TimestampMixin):
    verbose_name = "质量检验"
    """质检模型"""
    inspection_code = fields.CharField(max_length=100, unique=True, description="检验单号", index=True)
    inspection_type = fields.CharField(max_length=20, description="检验类型：IQC/IPQC/FQC/OQC", index=True)
    mo_code = fields.CharField(max_length=100, null=True, description="制造单编码", index=True)
    wo_code = fields.CharField(max_length=100, null=True, description="工单编码", index=True)
    material_code = fields.CharField(max_length=100, description="物料编码", index=True)
    material_name = fields.CharField(max_length=255, description="物料名称")
    batch_no = fields.CharField(max_length=100, null=True, description="批次号")
    quantity = fields.IntField(description="检验数量")
    qualified_quantity = fields.IntField(default=0, description="合格数量")
    unqualified_quantity = fields.IntField(default=0, description="不合格数量")
    inspection_result = fields.CharField(max_length=20, default="pending", description="检验结果：pending/qualified/unqualified", index=True)
    inspector = fields.CharField(max_length=100, null=True, description="检验员")
    inspection_items = fields.JSONField(null=True, description="检验项目及结果")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "mes_quality_inspection"

    async def to_dict(self):
        return {
            "id": self.id,
            "inspection_code": self.inspection_code,
            "inspection_type": self.inspection_type,
            "mo_code": self.mo_code,
            "wo_code": self.wo_code,
            "material_code": self.material_code,
            "material_name": self.material_name,
            "batch_no": self.batch_no,
            "quantity": self.quantity,
            "qualified_quantity": self.qualified_quantity,
            "unqualified_quantity": self.unqualified_quantity,
            "inspection_result": self.inspection_result,
            "inspector": self.inspector,
            "inspection_items": self.inspection_items,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class InspectionStandard(BaseModel, TimestampMixin):
    verbose_name = "检验标准"
    """检验标准模型"""
    standard_code = fields.CharField(max_length=100, unique=True, description="标准编码", index=True)
    standard_name = fields.CharField(max_length=255, description="标准名称")
    material_code = fields.CharField(max_length=100, null=True, description="适用物料编码")
    inspection_type = fields.CharField(max_length=20, description="检验类型：IQC/IPQC/FQC/OQC")
    items = fields.JSONField(null=True, description="检验项目列表")
    sampling_rule = fields.TextField(null=True, description="抽样规则")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "mes_inspection_standard"

    async def to_dict(self):
        return {
            "id": self.id,
            "standard_code": self.standard_code,
            "standard_name": self.standard_name,
            "material_code": self.material_code,
            "inspection_type": self.inspection_type,
            "items": self.items,
            "sampling_rule": self.sampling_rule,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }