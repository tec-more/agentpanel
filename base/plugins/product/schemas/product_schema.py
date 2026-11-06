"""
产品相关的Pydantic模型
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, computed_field
from decimal import Decimal


class ProductBase(BaseModel):
    """产品基础模型"""
    product_code: Optional[str] = Field(None, max_length=100, description="产品编码（从物料表自动填充）")
    name: str = Field(..., min_length=1, max_length=255, description="产品名称")
    description: Optional[str] = Field(None, description="产品描述")
    price: Decimal = Field(..., ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="销售价格")
    original_price: Optional[Decimal] = Field(None, ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="原价")
    stock: int = Field(default=0, ge=0, description="库存数量")
    sort: int = Field(default=0, ge=0, description="排序")
    category: Optional[str] = Field(None, max_length=50, description="产品分类")
    tags: Optional[List[str]] = Field(None, description="产品标签")
    images: Optional[List[str]] = Field(None, description="产品图片")
    is_active: bool = Field(default=True, description="是否上架")
    is_hot: bool = Field(default=False, description="是否热门")
    is_new: bool = Field(default=False, description="是否新品")
    is_stock_item: bool = Field(default=True, description="是否为库存商品：True-实物商品(需库存管理)，False-虚拟商品(如会员/充值)")
    material_id: Optional[int] = Field(None, description="关联的成品物料ID（库存商品模式下从物料表选取）")
    recharge_hours: Optional[int] = Field(None, ge=0, description="充值时长（小时）")
    bonus_hours: int = Field(default=0, ge=0, description="赠送时长（小时）")
    discount_description: Optional[str] = Field(None, max_length=255, description="优惠描述")

    @field_validator('original_price')
    @classmethod
    def validate_original_price(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        """验证原价必须大于销售价格"""
        if v is not None and 'price' in info.data:
            price = info.data['price']
            if v <= price:
                raise ValueError('原价必须大于销售价格')
        return v


class ProductCreate(ProductBase):
    """创建产品模型"""
    pass


class ProductUpdate(BaseModel):
    """更新产品模型"""
    product_code: Optional[str] = Field(None, max_length=100, description="产品编码")
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="产品名称")
    description: Optional[str] = Field(None, description="产品描述")
    price: Optional[Decimal] = Field(None, ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="销售价格")
    original_price: Optional[Decimal] = Field(None, ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="原价")
    stock: Optional[int] = Field(None, ge=0, description="库存数量")
    sort: Optional[int] = Field(None, ge=0, description="排序")
    category: Optional[str] = Field(None, max_length=50, description="产品分类")
    tags: Optional[List[str]] = Field(None, description="产品标签")
    images: Optional[List[str]] = Field(None, description="产品图片")
    is_active: Optional[bool] = Field(None, description="是否上架")
    is_hot: Optional[bool] = Field(None, description="是否热门")
    is_new: Optional[bool] = Field(None, description="是否新品")
    is_stock_item: Optional[bool] = Field(None, description="是否为库存商品")
    recharge_hours: Optional[int] = Field(None, ge=0, description="充值时长（小时）")
    bonus_hours: Optional[int] = Field(None, ge=0, description="赠送时长（小时）")
    discount_description: Optional[str] = Field(None, max_length=255, description="优惠描述")
    membership_level_id: Optional[int] = Field(None, description="关联的会员等级ID")

    model_config = {"populate_by_name": True}


class ProductResponse(BaseModel):
    """产品响应模型"""
    id: int
    product_code: Optional[str] = None
    name: str
    description: Optional[str] = None
    price: Decimal
    original_price: Optional[Decimal] = None
    stock: int
    sort: int
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    images: Optional[List[str]] = None
    is_active: bool
    is_hot: bool
    is_new: bool
    is_stock_item: bool
    view_count: int
    sales_count: int
    recharge_hours: Optional[int] = None
    bonus_hours: int
    discount_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # 计算字段
    @computed_field
    @property
    def current_price(self) -> Decimal:
        """当前价格（返回销售价格）"""
        return self.price

    @computed_field
    @property
    def has_discount(self) -> bool:
        """是否有优惠（有原价且原价大于销售价格）"""
        return self.original_price is not None and self.original_price > self.price

    @computed_field
    @property
    def discount_percentage(self) -> int:
        """折扣百分比"""
        if not self.has_discount:
            return 0
        return int((self.original_price - self.price) / self.original_price * 100)

    @computed_field
    @property
    def total_hours(self) -> int:
        """总时长（充值时长 + 赠送时长）"""
        recharge = self.recharge_hours or 0
        bonus = self.bonus_hours or 0
        return recharge + bonus

    class Config:
        from_attributes = True


class ProductListQuery(BaseModel):
    """产品列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    name: Optional[str] = Field(None, description="产品名称(模糊搜索)")
    category: Optional[str] = Field(None, description="产品分类")
    is_active: Optional[bool] = Field(None, description="是否上架")
    is_hot: Optional[bool] = Field(None, description="是否热门")
    is_new: Optional[bool] = Field(None, description="是否新品")


class ProductListResponse(BaseModel):
    """产品列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[ProductResponse] = Field(..., description="产品列表")


class ProductStockUpdate(BaseModel):
    """产品库存更新模型"""
    quantity: int = Field(..., description="库存变更数量（正数增加，负数减少）")

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        # 允许负数，但需要在服务层检查库存是否足够
        return v


class ProductSalesUpdate(BaseModel):
    """产品销售数量更新模型"""
    quantity: int = Field(..., ge=1, description="销售数量增加量")


class CategoryBase(BaseModel):
    """分类基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="分类名称")
    code: Optional[str] = Field(None, max_length=50, description="分类编码")
    parent_id: Optional[int] = Field(None, description="父分类ID")
    sort: int = Field(default=0, ge=0, description="排序")
    description: Optional[str] = Field(None, description="分类描述")
    is_active: bool = Field(default=True, description="是否启用")


class CategoryCreate(CategoryBase):
    """创建分类模型"""
    pass


class CategoryUpdate(BaseModel):
    """更新分类模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="分类名称")
    code: Optional[str] = Field(None, max_length=50, description="分类编码")
    parent_id: Optional[int] = Field(None, description="父分类ID")
    sort: Optional[int] = Field(None, ge=0, description="排序")
    description: Optional[str] = Field(None, description="分类描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class CategoryResponse(CategoryBase):
    """分类响应模型"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    """分类列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[CategoryResponse] = Field(..., description="分类列表")


class AttributeBase(BaseModel):
    """属性基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="属性名称")
    code: str = Field(..., min_length=1, max_length=50, description="属性编码")
    category: str = Field(default="both", description="属性类别：product/material/both")
    sort: int = Field(default=0, ge=0, description="排序")
    is_active: bool = Field(default=True, description="是否启用")


class AttributeCreate(AttributeBase):
    """创建属性模型"""
    pass


class AttributeUpdate(BaseModel):
    """更新属性模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="属性名称")
    code: Optional[str] = Field(None, min_length=1, max_length=50, description="属性编码")
    category: Optional[str] = Field(None, description="属性类别")
    sort: Optional[int] = Field(None, ge=0, description="排序")
    is_active: Optional[bool] = Field(None, description="是否启用")


class AttributeResponse(AttributeBase):
    """属性响应模型"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AttributeListResponse(BaseModel):
    """属性列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[AttributeResponse] = Field(..., description="属性列表")


class AttributeValueBase(BaseModel):
    """属性值基础模型"""
    attribute_id: int = Field(..., description="属性ID")
    value: str = Field(..., min_length=1, max_length=100, description="属性值")
    sort: int = Field(default=0, ge=0, description="排序")


class AttributeValueCreate(AttributeValueBase):
    """创建属性值模型"""
    pass


class AttributeValueUpdate(BaseModel):
    """更新属性值模型"""
    value: Optional[str] = Field(None, min_length=1, max_length=100, description="属性值")
    sort: Optional[int] = Field(None, ge=0, description="排序")


class AttributeValueResponse(AttributeValueBase):
    """属性值响应模型"""
    id: int
    attribute_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaterialVariantBase(BaseModel):
    """物料变体基础模型"""
    material_id: int = Field(..., description="物料ID")
    variant_code: str = Field(..., min_length=1, max_length=100, description="变体编码")
    attributes: Optional[Dict[str, str]] = Field(None, description="属性组合")
    specification: Optional[str] = Field(None, max_length=255, description="规格型号")
    unit: Optional[str] = Field(None, max_length=20, description="计量单位")
    initial_stock: int = Field(default=0, ge=0, description="初始库存")
    is_active: bool = Field(default=True, description="是否启用")


class MaterialVariantCreate(MaterialVariantBase):
    """创建物料变体模型"""
    pass


class MaterialVariantUpdate(BaseModel):
    """更新物料变体模型"""
    variant_code: Optional[str] = Field(None, min_length=1, max_length=100, description="变体编码")
    attributes: Optional[Dict[str, str]] = Field(None, description="属性组合")
    specification: Optional[str] = Field(None, max_length=255, description="规格型号")
    unit: Optional[str] = Field(None, max_length=20, description="计量单位")
    initial_stock: Optional[int] = Field(None, ge=0, description="初始库存")
    is_active: Optional[bool] = Field(None, description="是否启用")


class MaterialVariantResponse(MaterialVariantBase):
    """物料变体响应模型"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaterialVariantListResponse(BaseModel):
    """物料变体列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[MaterialVariantResponse] = Field(..., description="物料变体列表")


class ProductVariantBase(BaseModel):
    """产品变体基础模型"""
    product_id: int = Field(..., description="产品ID")
    sku: str = Field(..., min_length=1, max_length=100, description="SKU编码")
    attributes: Optional[Dict[str, str]] = Field(None, description="属性组合")
    price: Decimal = Field(..., ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="价格")
    original_price: Optional[Decimal] = Field(None, ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="原价")
    stock: int = Field(default=0, ge=0, description="库存数量")
    material_variant_id: Optional[int] = Field(None, description="关联物料变体ID")
    is_active: bool = Field(default=True, description="是否启用")


class ProductVariantCreate(ProductVariantBase):
    """创建产品变体模型"""
    pass


class ProductVariantUpdate(BaseModel):
    """更新产品变体模型"""
    sku: Optional[str] = Field(None, min_length=1, max_length=100, description="SKU编码")
    attributes: Optional[Dict[str, str]] = Field(None, description="属性组合")
    price: Optional[Decimal] = Field(None, ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="价格")
    original_price: Optional[Decimal] = Field(None, ge=Decimal("0.01"), max_digits=10, decimal_places=2, description="原价")
    stock: Optional[int] = Field(None, ge=0, description="库存数量")
    material_variant_id: Optional[int] = Field(None, description="关联物料变体ID")
    is_active: Optional[bool] = Field(None, description="是否启用")


class ProductVariantResponse(ProductVariantBase):
    """产品变体响应模型"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductVariantListResponse(BaseModel):
    """产品变体列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[ProductVariantResponse] = Field(..., description="产品变体列表")
