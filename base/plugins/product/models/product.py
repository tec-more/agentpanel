"""
产品数据模型
"""
try:
    from tortoise import fields
    from tortoise.models import Model
    from base.common.model import BaseModel, TimestampMixin
except ImportError:
    # 定义临时依赖，以便在没有base模块的情况下也能工作
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


class ProductCategory(BaseModel, TimestampMixin):
    verbose_name = "产品分类"
    """产品分类模型"""
    name = fields.CharField(max_length=50, unique=True, description="分类名称", index=True)
    code = fields.CharField(max_length=50, unique=True, null=True, description="分类编码", index=True)
    parent_id = fields.IntField(null=True, description="父分类ID")
    sort = fields.IntField(default=0, description="排序", index=True)
    description = fields.TextField(null=True, description="分类描述")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "product_category"

    async def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "parent_id": self.parent_id,
            "sort": self.sort,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class ProductVariant(BaseModel, TimestampMixin):
    verbose_name = "产品变体"
    """产品变体模型"""
    product = fields.ForeignKeyField("models.Product", on_delete=fields.CASCADE, description="关联产品")
    sku = fields.CharField(max_length=100, unique=True, description="SKU编码", index=True)
    attributes = fields.JSONField(null=True, description="属性组合")
    price = fields.DecimalField(max_digits=10, decimal_places=2, description="价格")
    original_price = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="原价")
    stock = fields.IntField(default=0, description="库存数量")
    material_variant_id = fields.IntField(null=True, description="关联物料变体ID")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "product_variant"

    @property
    def total_hours(self):
        if self.recharge_hours and self.bonus_hours:
            return self.recharge_hours + self.bonus_hours
        return self.recharge_hours or 0

    async def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "sku": self.sku,
            "attributes": self.attributes,
            "price": float(self.price) if self.price and hasattr(self.price, "__float__") else self.price,
            "original_price": float(self.original_price) if self.original_price and hasattr(self.original_price, "__float__") else self.original_price,
            "stock": self.stock,
            "material_variant_id": self.material_variant_id,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class Product(BaseModel, TimestampMixin):
    verbose_name = "产品"
    """产品模型"""
    product_code = fields.CharField(max_length=100, unique=True, null=True, description="产品编码", index=True)
    name = fields.CharField(max_length=255, unique=True, description="产品名称", index=True)
    description = fields.TextField(null=True, description="产品描述")
    price = fields.DecimalField(max_digits=10, decimal_places=2, description="价格")
    original_price = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="原价")
    sale_price = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="优惠价")
    stock = fields.IntField(default=0, description="库存数量")
    sort = fields.IntField(default=0, description="排序", index=True)
    category = fields.CharField(max_length=50, null=True, description="产品分类", index=True)
    tags = fields.JSONField(null=True, description="产品标签")
    images = fields.JSONField(null=True, description="产品图片")
    is_active = fields.BooleanField(default=True, description="是否上架", index=True)
    is_hot = fields.BooleanField(default=False, description="是否热门", index=True)
    is_new = fields.BooleanField(default=False, description="是否新品", index=True)
    view_count = fields.IntField(default=0, description="浏览次数", index=True)
    sales_count = fields.IntField(default=0, description="销售数量", index=True)
    
    # 多单位支持字段
    uom_id = fields.IntField(null=True, description="主单位ID")
    uom_code = fields.CharField(max_length=20, default="unit", description="主单位编码")
    uom_name = fields.CharField(max_length=50, default="件", description="主单位名称")
    uom_category = fields.CharField(max_length=50, default="unit", description="单位类别：unit/weight/length/volume/time")
    
    secondary_uom_id = fields.IntField(null=True, description="辅助单位ID")
    secondary_uom_code = fields.CharField(max_length=20, null=True, description="辅助单位编码")
    secondary_uom_name = fields.CharField(max_length=50, null=True, description="辅助单位名称")
    conversion_factor = fields.DecimalField(max_digits=12, decimal_places=4, default=1, description="换算比例（主单位 = 辅助单位 × 换算比例）")
    
    # 充值相关字段
    recharge_hours = fields.IntField(null=True, description="充值时长（小时）")
    bonus_hours = fields.IntField(default=0, description="赠送时长（小时）")
    discount_description = fields.CharField(max_length=255, null=True, description="优惠描述")

    # 会员套餐相关字段（混合方案）
    membership_level_id = fields.IntField(null=True, description="关联的会员等级ID")
    product_type = fields.CharField(max_length=50, default="item", description="产品类型：item/membership/hours")
    price_mode = fields.CharField(
        max_length=20,
        default="dynamic",
        description="价格模式：dynamic(跟随会员等级) 或 fixed(独立定价)"
    )
    is_stock_item = fields.BooleanField(default=True, description="是否为库存商品：True-实物商品(需库存管理)，False-虚拟商品(如会员/充值)")

    class Meta:
        table = "product"

    @property
    def current_price(self):
        """获取当前价格（返回price字段）"""
        return float(self.price)

    @property
    def has_discount(self) -> bool:
        """判断是否有优惠"""
        return self.original_price is not None and float(self.price) < float(self.original_price)

    @property
    def discount_percentage(self) -> int:
        """计算折扣百分比"""
        if not self.has_discount:
            return 0
        original = float(self.original_price)
        current = float(self.price)
        return int((original - current) / original * 100)

    @property
    def total_hours(self) -> int:
        """获取总时长（充值时长 + 赠送时长）"""
        recharge = self.recharge_hours or 0
        bonus = self.bonus_hours or 0
        return recharge + bonus

    async def get_effective_config(self) -> dict:
        """
        获取有效的产品配置（混合方案）

        Returns:
            dict: 包含 hours, price, discount_percentage, duration_days, features 等配置
        """
        # 动态模式：从会员等级获取最新配置
        if self.price_mode == "dynamic" and self.membership_level_id:
            try:
                from base.plugins.customer.models.membership import MembershipLevel
                level = await MembershipLevel.get_or_none(id=self.membership_level_id)
                if level:
                    return {
                        "hours": level.hours,
                        "price": float(level.price),
                        "discount_percentage": level.discount_percentage,
                        "duration_days": level.duration_days,
                        "features": level.features,
                        "mode": "dynamic",
                        "membership_level_name": level.name,
                        "membership_level_type": level.level_type
                    }
            except Exception as e:
                print(f"[Product] 获取会员等级配置失败: {e}")

        # 固定模式或没有会员等级：使用产品自身配置
        extra_info = self.extra_info if hasattr(self, 'extra_info') else None
        return {
            "hours": extra_info.get("hours") if extra_info else (self.recharge_hours or 0),
            "price": float(self.price),
            "discount_percentage": extra_info.get("discount_percentage", 0) if extra_info else 0,
            "duration_days": extra_info.get("duration_days", 0) if extra_info else 0,
            "features": extra_info.get("features", []) if extra_info else [],
            "mode": "fixed",
            "membership_level_name": extra_info.get("membership_level_name") if extra_info else self.name,
            "membership_level_type": extra_info.get("membership_level_type") if extra_info else None
        }

    async def to_dict(self):
        """转换为字典"""
        # 获取有效配置（包含动态或固定模式的信息）
        effective_config = await self.get_effective_config()

        data = {
            "id": self.id,
            "product_code": self.product_code,
            "name": self.name,
            "description": self.description,
            "price": float(self.price) if hasattr(self.price, "__float__") else self.price,
            "original_price": float(self.original_price) if self.original_price and hasattr(self.original_price, "__float__") else self.original_price,
            "sale_price": float(self.sale_price) if self.sale_price and hasattr(self.sale_price, "__float__") else self.sale_price,
            "current_price": self.current_price,
            "has_discount": self.has_discount,
            "discount_percentage": self.discount_percentage,
            "stock": self.stock,
            "sort": self.sort,
            "category": self.category,
            "tags": self.tags,
            "images": self.images,
            "is_active": self.is_active,
            "is_hot": self.is_hot,
            "is_new": self.is_new,
            "view_count": self.view_count,
            "sales_count": self.sales_count,
            # 多单位支持
            "uom_id": self.uom_id,
            "uom_code": self.uom_code,
            "uom_name": self.uom_name,
            "uom_category": self.uom_category,
            "secondary_uom_id": self.secondary_uom_id,
            "secondary_uom_code": self.secondary_uom_code,
            "secondary_uom_name": self.secondary_uom_name,
            "conversion_factor": float(self.conversion_factor) if self.conversion_factor and hasattr(self.conversion_factor, "__float__") else self.conversion_factor,
            # 充值相关字段
            "recharge_hours": self.recharge_hours,
            "bonus_hours": self.bonus_hours,
            "total_hours": self.total_hours,
            "discount_description": self.discount_description,
            # 新增：会员套餐相关字段
            "membership_level_id": self.membership_level_id,
            "product_type": self.product_type,
            "price_mode": self.price_mode,
            # 新增：有效配置信息
            "effective_config": effective_config,
            "is_active": self.is_active,
            "is_hot": self.is_hot,
            "is_new": self.is_new,
            "is_stock_item": self.is_stock_item,
            "view_count": self.view_count,
            "sales_count": self.sales_count,
            "recharge_hours": self.recharge_hours,
            "bonus_hours": self.bonus_hours,
            "total_hours": self.total_hours,
            "discount_description": self.discount_description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        return data