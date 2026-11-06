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


class Material(BaseModel, TimestampMixin):
    verbose_name = "物料"
    """物料主数据模型"""
    product_id = fields.IntField(null=True, description="产品ID", index=True)
    material_code = fields.CharField(max_length=100, unique=True, description="物料编码", index=True)
    material_name = fields.CharField(max_length=255, description="物料名称", index=True)
    material_type = fields.CharField(max_length=50, description="物料类型：raw/finished/semi/fixture", index=True)
    unit = fields.CharField(max_length=20, description="计量单位")
    specification = fields.CharField(max_length=255, null=True, description="规格型号")
    drawing_code = fields.CharField(max_length=100, null=True, description="图纸编号", index=True)
    drawing_url = fields.CharField(max_length=500, null=True, description="图纸文件地址")
    description = fields.TextField(null=True, description="物料描述")
    initial_stock = fields.IntField(default=0, description="初始库存数量")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "mes_material"

    async def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "material_code": self.material_code,
            "material_name": self.material_name,
            "material_type": self.material_type,
            "unit": self.unit,
            "specification": self.specification,
            "drawing_code": self.drawing_code,
            "drawing_url": self.drawing_url,
            "description": self.description,
            "initial_stock": self.initial_stock,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class MaterialVariant(BaseModel, TimestampMixin):
    verbose_name = "物料变体"
    """物料变体模型"""
    material = fields.ForeignKeyField("models.Material", on_delete=fields.CASCADE, description="关联物料")
    variant_code = fields.CharField(max_length=100, unique=True, description="变体编码", index=True)
    attributes = fields.JSONField(null=True, description="属性组合")
    specification = fields.CharField(max_length=255, null=True, description="规格型号")
    unit = fields.CharField(max_length=20, null=True, description="计量单位")
    initial_stock = fields.IntField(default=0, description="初始库存数量")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "mes_material_variant"

    async def to_dict(self):
        return {
            "id": self.id,
            "material_id": self.material_id,
            "variant_code": self.variant_code,
            "attributes": self.attributes,
            "specification": self.specification,
            "unit": self.unit,
            "initial_stock": self.initial_stock,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class BomVersion(BaseModel, TimestampMixin):
    verbose_name = "BOM版本"
    """BOM版本管理模型"""
    product_id = fields.IntField(null=True, description="成品产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="成品编码", index=True)
    product_name = fields.CharField(max_length=255, description="成品名称")
    version = fields.CharField(max_length=20, description="版本号")
    status = fields.CharField(max_length=20, default="draft", description="版本状态：draft/active/obsolete", index=True)
    description = fields.TextField(null=True, description="版本描述")
    ecn_code = fields.CharField(max_length=100, null=True, description="工程变更通知编号")
    effective_date = fields.DateField(null=True, description="生效日期")

    class Meta:
        table = "mes_bom_version"
        unique_together = ("product_code", "version")

    async def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
            "ecn_code": self.ecn_code,
            "effective_date": self.effective_date.strftime("%Y-%m-%d") if self.effective_date else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class Bom(BaseModel, TimestampMixin):
    verbose_name = "物料清单"
    """物料清单模型"""
    product_id = fields.IntField(null=True, description="成品产品ID", index=True)
    product_code = fields.CharField(max_length=100, description="成品编码", index=True)
    product_name = fields.CharField(max_length=255, description="成品名称")
    version = fields.CharField(max_length=20, default="V1.0", description="版本号")
    level = fields.IntField(default=1, description="BOM层级")
    parent_item_code = fields.CharField(max_length=100, null=True, description="父项编码")
    item_id = fields.IntField(null=True, description="物料产品ID", index=True)
    item_code = fields.CharField(max_length=100, description="物料编码", index=True)
    item_name = fields.CharField(max_length=255, description="物料名称")
    quantity = fields.DecimalField(max_digits=15, decimal_places=6, description="用量")
    unit = fields.CharField(max_length=20, description="计量单位")
    scrap_rate = fields.DecimalField(max_digits=5, decimal_places=4, default=0, description="损耗率")
    drawing_code = fields.CharField(max_length=100, null=True, description="装配图编号", index=True)
    drawing_url = fields.CharField(max_length=500, null=True, description="装配图文件地址")
    remark = fields.TextField(null=True, description="备注")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "mes_bom"

    async def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "version": self.version,
            "level": self.level,
            "parent_item_code": self.parent_item_code,
            "item_id": self.item_id,
            "item_code": self.item_code,
            "item_name": self.item_name,
            "quantity": float(self.quantity) if hasattr(self.quantity, "__float__") else self.quantity,
            "unit": self.unit,
            "scrap_rate": float(self.scrap_rate) if hasattr(self.scrap_rate, "__float__") else self.scrap_rate,
            "drawing_code": self.drawing_code,
            "drawing_url": self.drawing_url,
            "remark": self.remark,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class WorkCenter(BaseModel, TimestampMixin):
    verbose_name = "工作中心"
    """工作中心模型"""
    work_center_code = fields.CharField(max_length=100, unique=True, description="工作中心编码", index=True)
    work_center_name = fields.CharField(max_length=255, description="工作中心名称", index=True)
    department = fields.CharField(max_length=100, null=True, description="所属部门")
    location = fields.CharField(max_length=255, null=True, description="位置")
    capacity = fields.IntField(default=1, description="产能")
    description = fields.TextField(null=True, description="描述")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "mes_work_center"

    async def to_dict(self):
        return {
            "id": self.id,
            "work_center_code": self.work_center_code,
            "work_center_name": self.work_center_name,
            "department": self.department,
            "location": self.location,
            "capacity": self.capacity,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class Process(BaseModel, TimestampMixin):
    verbose_name = "工序"
    """工艺/工序模型"""
    process_code = fields.CharField(max_length=100, unique=True, description="工序编码", index=True)
    process_name = fields.CharField(max_length=255, description="工序名称", index=True)
    process_type = fields.CharField(max_length=50, description="工艺类型")
    sequence = fields.IntField(default=0, description="工序顺序", index=True)
    work_center_code = fields.CharField(max_length=100, null=True, description="工作中心编码")
    work_center_name = fields.CharField(max_length=255, null=True, description="工作中心名称")
    standard_time = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="标准工时(分钟)")
    drawing_code = fields.CharField(max_length=100, null=True, description="图纸编号", index=True)
    description = fields.TextField(null=True, description="描述")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    is_subcontracting = fields.BooleanField(default=False, description="是否委外工序")

    class Meta:
        table = "mes_process"

    async def to_dict(self):
        return {
            "id": self.id,
            "process_code": self.process_code,
            "process_name": self.process_name,
            "process_type": self.process_type,
            "sequence": self.sequence,
            "work_center_code": self.work_center_code,
            "work_center_name": self.work_center_name,
            "standard_time": float(self.standard_time) if self.standard_time and hasattr(self.standard_time, "__float__") else self.standard_time,
            "drawing_code": self.drawing_code,
            "description": self.description,
            "is_active": self.is_active,
            "is_subcontracting": self.is_subcontracting,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class Route(BaseModel, TimestampMixin):
    verbose_name = "生产路线"
    """生产路线模型"""
    route_code = fields.CharField(max_length=100, unique=True, description="路线编码", index=True)
    route_name = fields.CharField(max_length=255, description="路线名称", index=True)
    product_code = fields.CharField(max_length=100, description="产品编码", index=True)
    product_name = fields.CharField(max_length=255, description="产品名称")
    bom_code = fields.CharField(max_length=100, null=True, description="关联BOM编码（产品编码）", index=True)
    bom_version = fields.CharField(max_length=20, null=True, description="关联BOM版本号")
    version = fields.CharField(max_length=20, default="V1.0", description="版本号")
    description = fields.TextField(null=True, description="描述")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "mes_route"

    async def to_dict(self):
        return {
            "id": self.id,
            "route_code": self.route_code,
            "route_name": self.route_name,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "bom_code": self.bom_code,
            "bom_version": self.bom_version,
            "version": self.version,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class RouteProcess(BaseModel, TimestampMixin):
    """生产路线工序关联模型"""
    route_code = fields.CharField(max_length=100, description="路线编码", index=True)
    process_code = fields.CharField(max_length=100, description="工序编码", index=True)
    process_name = fields.CharField(max_length=255, description="工序名称")
    sequence = fields.IntField(default=0, description="工序顺序", index=True)
    work_center_code = fields.CharField(max_length=100, null=True, description="工作中心编码")
    work_center_name = fields.CharField(max_length=255, null=True, description="工作中心名称")
    is_subcontracting = fields.BooleanField(default=False, description="是否委外工序")

    class Meta:
        table = "mes_route_process"

    async def to_dict(self):
        return {
            "id": self.id,
            "route_code": self.route_code,
            "process_code": self.process_code,
            "process_name": self.process_name,
            "sequence": self.sequence,
            "work_center_code": self.work_center_code,
            "work_center_name": self.work_center_name,
            "is_subcontracting": self.is_subcontracting,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }