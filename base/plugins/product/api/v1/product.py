"""
产品模块API
"""
from fastapi import APIRouter, Depends, status, Query
from typing import Optional
from decimal import Decimal

# 导入响应类
try:
    from base.common.response import SuccessResponse, ErrorResponse
except ImportError:
    # 定义临时响应类，以便在没有base模块的情况下也能工作
    class SuccessResponse:
        def __init__(self, data=None, msg="操作成功"):
            self.data = data
            self.msg = msg
            self.success = True

    class ErrorResponse:
        def __init__(self, msg="操作失败", status_code=400):
            self.msg = msg
            self.success = False
            self.status_code = status_code

# 导入安全相关模块
try:
    from base.common.security import get_current_user_id
except ImportError:
    # 定义临时依赖，以便在没有base模块的情况下也能工作
    from fastapi import HTTPException
    async def get_current_user_id():
        raise HTTPException(status_code=401, detail="未授权")

# 导入Pydantic模式和服务
try:
    from base.plugins.product.schemas.product_schema import (
        ProductResponse,
        ProductCreate,
        ProductUpdate,
        ProductListQuery,
        ProductListResponse,
        ProductStockUpdate,
        ProductSalesUpdate,
    )
    from base.plugins.product.services.product_service import ProductService
except ImportError:
    # 定义临时模式和服务，以便在没有实现的情况下也能工作
    from pydantic import BaseModel
    from typing import List, Dict, Any
    from decimal import Decimal

    class ProductBase(BaseModel):
        name: str
        price: Decimal
        stock: int = 0
        category: Optional[str] = None

    class ProductCreate(ProductBase):
        description: Optional[str] = None
        tags: Optional[List[str]] = None
        images: Optional[List[str]] = None
        is_active: bool = True
        is_hot: bool = False
        is_new: bool = False

    class ProductUpdate(BaseModel):
        name: Optional[str] = None
        description: Optional[str] = None
        price: Optional[Decimal] = None
        stock: Optional[int] = None
        category: Optional[str] = None
        tags: Optional[List[str]] = None
        images: Optional[List[str]] = None
        is_active: Optional[bool] = None
        is_hot: Optional[bool] = None
        is_new: Optional[bool] = None

    class ProductResponse(ProductBase):
        id: int
        description: Optional[str] = None
        tags: Optional[List[str]] = None
        images: Optional[List[str]] = None
        is_active: bool
        is_hot: bool
        is_new: bool
        view_count: int
        sales_count: int

        class Config:
            from_attributes = True

    class ProductListQuery(BaseModel):
        page: int = 1
        page_size: int = 10
        name: Optional[str] = None
        category: Optional[str] = None
        is_active: Optional[bool] = None
        is_hot: Optional[bool] = None
        is_new: Optional[bool] = None

    class ProductListResponse(BaseModel):
        total: int
        page: int
        page_size: int
        items: List[ProductResponse]

    class ProductStockUpdate(BaseModel):
        quantity: int

    class ProductSalesUpdate(BaseModel):
        quantity: int

    class ProductService:
        @staticmethod
        async def create_product(product_data):
            pass

        @staticmethod
        async def update_product(product_id, product_data):
            pass

        @staticmethod
        async def get_product_by_id(product_id):
            pass

        @staticmethod
        async def delete_product(product_id):
            pass

        @staticmethod
        async def toggle_product_status(product_id):
            pass

        @staticmethod
        async def update_stock(product_id, quantity):
            pass

        @staticmethod
        async def update_sales_count(product_id, quantity):
            pass

        @staticmethod
        async def increment_view_count(product_id):
            pass

        @staticmethod
        async def get_product_list(page, page_size, **filters):
            pass

        @staticmethod
        async def get_product_categories():
            pass

# 创建路由实例
product_router = APIRouter(
    prefix="",
    tags=["产品管理"]
)

try:
    from base.plugins.product.services.product_service import CategoryService
    from base.plugins.product.services.variant_service import AttributeService, AttributeValueService, MaterialVariantService, ProductVariantService
    from base.plugins.product.schemas.product_schema import CategoryCreate, CategoryUpdate
    CATEGORY_AVAILABLE = True
    ATTRIBUTE_AVAILABLE = True
except ImportError:
    CategoryService = None
    AttributeService = None
    AttributeValueService = None
    MaterialVariantService = None
    ProductVariantService = None
    CATEGORY_AVAILABLE = False
    ATTRIBUTE_AVAILABLE = False


@product_router.get("/categories", summary="获取产品分类列表")
async def get_category_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    name: Optional[str] = Query(None, description="分类名称关键词"),
    parent_id: Optional[int] = Query(None, description="父分类ID"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    try:
        items, total = await CategoryService.get_category_list(
            page=page, page_size=page_size,
            name=name, parent_id=parent_id, is_active=is_active
        )
        return SuccessResponse(data={"items": items, "total": total, "page": page, "page_size": page_size}, msg="获取分类列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/categories/options", summary="获取产品分类选项（下拉选择用）")
async def get_category_options():
    try:
        options = await CategoryService.get_category_options()
        return SuccessResponse(data=options, msg="获取分类选项成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/categories/{category_id}", summary="获取产品分类详情")
async def get_category(category_id: int):
    try:
        category = await CategoryService.get_category_by_id(category_id)
        if not category:
            return ErrorResponse(msg="分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=category, msg="获取分类详情成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.post("/categories", summary="创建产品分类")
async def create_category(data: CategoryCreate):
    try:
        category = await CategoryService.create_category(data.dict())
        return SuccessResponse(data=category, msg="分类创建成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.put("/categories/{category_id}", summary="更新产品分类")
async def update_category(category_id: int, data: CategoryUpdate):
    try:
        category = await CategoryService.update_category(category_id, data.dict(exclude_unset=True))
        if not category:
            return ErrorResponse(msg="分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=category, msg="分类更新成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.delete("/categories/{category_id}", summary="删除产品分类")
async def delete_category(category_id: int):
    try:
        success = await CategoryService.delete_category(category_id)
        if not success:
            return ErrorResponse(msg="分类不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data={"message": "分类删除成功"}, msg="分类删除成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/attributes", summary="获取产品属性列表")
async def get_attribute_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    name: Optional[str] = Query(None, description="属性名称关键词"),
    category: Optional[str] = Query(None, description="属性类别"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    try:
        items, total = await AttributeService.get_attribute_list(
            page=page, page_size=page_size,
            name=name, category=category, is_active=is_active
        )
        return SuccessResponse(data={"items": items, "total": total, "page": page, "page_size": page_size}, msg="获取属性列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/attributes/options", summary="获取产品属性选项（下拉选择用）")
async def get_attribute_options(
    category: Optional[str] = Query(None, description="属性类别")
):
    try:
        options = await AttributeService.get_attribute_options(category=category)
        return SuccessResponse(data=options, msg="获取属性选项成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/attributes/{attribute_id}", summary="获取产品属性详情")
async def get_attribute(attribute_id: int):
    try:
        attribute = await AttributeService.get_attribute_by_id(attribute_id)
        if not attribute:
            return ErrorResponse(msg="属性不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=attribute, msg="获取属性详情成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.post("/attributes", summary="创建产品属性")
async def create_attribute(data: dict):
    try:
        attribute = await AttributeService.create_attribute(data)
        return SuccessResponse(data=attribute, msg="属性创建成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.put("/attributes/{attribute_id}", summary="更新产品属性")
async def update_attribute(attribute_id: int, data: dict):
    try:
        attribute = await AttributeService.update_attribute(attribute_id, data)
        if not attribute:
            return ErrorResponse(msg="属性不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=attribute, msg="属性更新成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.delete("/attributes/{attribute_id}", summary="删除产品属性")
async def delete_attribute(attribute_id: int):
    try:
        success = await AttributeService.delete_attribute(attribute_id)
        if not success:
            return ErrorResponse(msg="属性不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data={"message": "属性删除成功"}, msg="属性删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/attributes/{attribute_id}/values", summary="获取属性值列表")
async def get_attribute_values(
    attribute_id: int,
    product_category_id: Optional[int] = Query(None, description="产品分类ID，过滤该分类可用的属性值")
):
    try:
        values = await AttributeValueService.get_attribute_values(attribute_id, product_category_id)
        return SuccessResponse(data=values, msg="获取属性值列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.post("/attributes/values", summary="创建属性值")
async def create_attribute_value(data: dict):
    try:
        value = await AttributeValueService.create_attribute_value(data)
        return SuccessResponse(data=value, msg="属性值创建成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.put("/attributes/values/{value_id}", summary="更新属性值")
async def update_attribute_value(value_id: int, data: dict):
    try:
        value = await AttributeValueService.update_attribute_value(value_id, data)
        if not value:
            return ErrorResponse(msg="属性值不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=value, msg="属性值更新成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.delete("/attributes/values/{value_id}", summary="删除属性值")
async def delete_attribute_value(value_id: int):
    try:
        success = await AttributeValueService.delete_attribute_value(value_id)
        if not success:
            return ErrorResponse(msg="属性值不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data={"message": "属性值删除成功"}, msg="属性值删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/material-variants", summary="获取物料变体列表")
async def get_material_variant_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    material_id: Optional[int] = Query(None, description="物料ID"),
    variant_code: Optional[str] = Query(None, description="变体编码"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    try:
        items, total = await MaterialVariantService.get_material_variant_list(
            page=page, page_size=page_size,
            material_id=material_id, variant_code=variant_code, is_active=is_active
        )
        return SuccessResponse(data={"items": items, "total": total, "page": page, "page_size": page_size}, msg="获取物料变体列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/material-variants/{variant_id}", summary="获取物料变体详情")
async def get_material_variant(variant_id: int):
    try:
        variant = await MaterialVariantService.get_material_variant_by_id(variant_id)
        if not variant:
            return ErrorResponse(msg="物料变体不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=variant, msg="获取物料变体详情成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.post("/material-variants", summary="创建物料变体")
async def create_material_variant(data: dict):
    try:
        variant = await MaterialVariantService.create_material_variant(data)
        return SuccessResponse(data=variant, msg="物料变体创建成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.put("/material-variants/{variant_id}", summary="更新物料变体")
async def update_material_variant(variant_id: int, data: dict):
    try:
        variant = await MaterialVariantService.update_material_variant(variant_id, data)
        if not variant:
            return ErrorResponse(msg="物料变体不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=variant, msg="物料变体更新成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.delete("/material-variants/{variant_id}", summary="删除物料变体")
async def delete_material_variant(variant_id: int):
    try:
        success = await MaterialVariantService.delete_material_variant(variant_id)
        if not success:
            return ErrorResponse(msg="物料变体不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data={"message": "物料变体删除成功"}, msg="物料变体删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/variants", summary="获取产品变体列表")
async def get_product_variant_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    product_id: Optional[int] = Query(None, description="产品ID"),
    sku: Optional[str] = Query(None, description="SKU"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    try:
        items, total = await ProductVariantService.get_product_variant_list(
            page=page, page_size=page_size,
            product_id=product_id, sku=sku, is_active=is_active
        )
        return SuccessResponse(data={"items": items, "total": total, "page": page, "page_size": page_size}, msg="获取产品变体列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/variants/{variant_id}", summary="获取产品变体详情")
async def get_product_variant(variant_id: int):
    try:
        variant = await ProductVariantService.get_product_variant_by_id(variant_id)
        if not variant:
            return ErrorResponse(msg="产品变体不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=variant, msg="获取产品变体详情成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.post("/variants", summary="创建产品变体")
async def create_product_variant(data: dict):
    try:
        variant = await ProductVariantService.create_product_variant(data)
        return SuccessResponse(data=variant, msg="产品变体创建成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.put("/variants/{variant_id}", summary="更新产品变体")
async def update_product_variant(variant_id: int, data: dict):
    try:
        variant = await ProductVariantService.update_product_variant(variant_id, data)
        if not variant:
            return ErrorResponse(msg="产品变体不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data=variant, msg="产品变体更新成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.delete("/variants/{variant_id}", summary="删除产品变体")
async def delete_product_variant(variant_id: int):
    try:
        success = await ProductVariantService.delete_product_variant(variant_id)
        if not success:
            return ErrorResponse(msg="产品变体不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(data={"message": "产品变体删除成功"}, msg="产品变体删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


# 为每个路由添加单数和复数两种路径
@product_router.post("/", summary="创建产品", status_code=status.HTTP_201_CREATED)
async def create_product(
        product_data: ProductCreate
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    创建新产品

    Args:
        product_data: 产品创建数据
        current_user_id: 当前用户ID

    Returns:
        创建成功的产品信息
    """
    try:
        product = await ProductService.create_product(product_data)
        # 使用to_dict方法确保datetime字段被正确转换
        if hasattr(product, 'to_dict'):
            product_dict = await product.to_dict()
        elif hasattr(product, 'dict'):
            product_dict = product.dict()
        else:
            product_dict = dict(product)
        return SuccessResponse(data=product_dict, msg="产品创建成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/list", summary="获取产品列表(分页)")
async def get_product_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=2000, description="每页数量"),
        name: Optional[str] = Query(None, description="产品名称(模糊搜索)"),
        category: Optional[str] = Query(None, description="产品分类"),
        is_active: Optional[bool] = Query(None, description="是否上架"),
        is_hot: Optional[bool] = Query(None, description="是否热门"),
        is_new: Optional[bool] = Query(None, description="是否新品"),
        is_stock_item: Optional[bool] = Query(None, description="是否库存商品")
):
    """
    获取产品列表(分页)

    Args:
        page: 页码
        page_size: 每页数量
        name: 产品名称(模糊搜索)
        category: 产品分类
        is_active: 是否上架
        is_hot: 是否热门
        is_new: 是否新品
        is_stock_item: 是否库存商品

    Returns:
        产品列表
    """
    try:
        products, total = await ProductService.get_product_list(
            page=page,
            page_size=page_size,
            name=name,
            category=category,
            is_active=is_active,
            is_hot=is_hot,
            is_new=is_new,
            is_stock_item=is_stock_item
        )

        # 转换为字典列表
        product_list = []
        for product in products:
            if hasattr(product, 'to_dict'):
                product_dict = await product.to_dict()
            elif hasattr(product, 'dict'):
                product_dict = product.dict()
            else:
                product_dict = dict(product)
            product_list.append(product_dict)

        response_data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": product_list
        }

        return SuccessResponse(data=response_data)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/item/{product_id:int}", summary="获取产品详情")
async def get_product_detail(
        product_id: int
):
    """
    获取产品详情

    Args:
        product_id: 产品ID
        current_user_id: 当前用户ID

    Returns:
        产品详细信息
    """
    try:
        product = await ProductService.get_by_id(product_id)
        if not product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)
        # 增加浏览次数
        await ProductService.increment_view_count(product_id)
        if hasattr(product, 'to_dict'):
            product_dict = await product.to_dict()
        elif hasattr(product, 'dict'):
            product_dict = product.dict()
        else:
            product_dict = dict(product)
        return SuccessResponse(data=product_dict)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.put("/item/{product_id:int}", summary="更新产品信息")
async def update_product(
        product_id: int,
        product_data: ProductUpdate
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    更新产品信息

    Args:
        product_id: 产品ID
        product_data: 更新数据
        current_user_id: 当前用户ID

    Returns:
        更新后的产品信息
    """
    try:
        updated_product = await ProductService.update_product(product_id, product_data)
        if not updated_product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)
        if hasattr(updated_product, 'to_dict'):
            product_dict = await updated_product.to_dict()
        elif hasattr(updated_product, 'dict'):
            product_dict = updated_product.dict()
        else:
            product_dict = dict(updated_product)
        return SuccessResponse(data=product_dict, msg="产品更新成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.delete("/item/{product_id:int}", summary="删除产品")
async def delete_product(
        product_id: int
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    删除产品

    Args:
        product_id: 产品ID
        current_user_id: 当前用户ID

    Returns:
        删除结果
    """
    try:
        success = await ProductService.delete_product(product_id)
        if not success:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)
        return SuccessResponse(msg="产品删除成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.delete("/batch", summary="批量删除产品")
async def batch_delete_product(
        request_data: dict
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    批量删除产品

    Args:
        request_data: 包含ids数组的请求体
        current_user_id: 当前用户ID

    Returns:
        删除结果
    """
    try:
        ids = request_data.get("ids", [])
        if not ids:
            return ErrorResponse(msg="请选择要删除的产品", status_code=status.HTTP_400_BAD_REQUEST)

        success_count = 0
        for product_id in ids:
            success = await ProductService.delete_product(product_id)
            if success:
                success_count += 1

        return SuccessResponse(msg=f"成功删除{success_count}/{len(ids)}个产品")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.patch("/item/{product_id:int}/toggle-status", summary="切换产品上架状态")
async def toggle_product_status(
        product_id: int
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    切换产品上架状态

    Args:
        product_id: 产品ID
        current_user_id: 当前用户ID

    Returns:
        更新后的产品信息
    """
    try:
        updated_product = await ProductService.toggle_product_status(product_id)
        if not updated_product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)
        if hasattr(updated_product, 'to_dict'):
            product_dict = await updated_product.to_dict()
        elif hasattr(updated_product, 'dict'):
            product_dict = updated_product.dict()
        else:
            product_dict = dict(updated_product)
        status_text = "上架" if updated_product.is_active else "下架"
        return SuccessResponse(data=product_dict, msg=f"产品已{status_text}")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.patch("/item/{product_id:int}/stock", summary="更新产品库存")
async def update_product_stock(
        product_id: int,
        stock_data: ProductStockUpdate
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    更新产品库存

    Args:
        product_id: 产品ID
        stock_data: 库存更新数据
        current_user_id: 当前用户ID

    Returns:
        更新后的产品信息
    """
    try:
        updated_product = await ProductService.update_stock(product_id, stock_data.quantity)
        if not updated_product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)
        if hasattr(updated_product, 'to_dict'):
            product_dict = await updated_product.to_dict()
        elif hasattr(updated_product, 'dict'):
            product_dict = updated_product.dict()
        else:
            product_dict = dict(updated_product)
        return SuccessResponse(data=product_dict, msg="库存更新成功")
    except ValueError as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.patch("/item/{product_id:int}/sales", summary="更新产品销售数量")
async def update_product_sales(
        product_id: int,
        sales_data: ProductSalesUpdate
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    更新产品销售数量

    Args:
        product_id: 产品ID
        sales_data: 销售数量更新数据
        current_user_id: 当前用户ID

    Returns:
        更新后的产品信息
    """
    try:
        updated_product = await ProductService.update_sales_count(product_id, sales_data.quantity)
        if not updated_product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)
        if hasattr(updated_product, 'to_dict'):
            product_dict = await updated_product.to_dict()
        elif hasattr(updated_product, 'dict'):
            product_dict = updated_product.dict()
        else:
            product_dict = dict(updated_product)
        return SuccessResponse(data=product_dict, msg="销售数量更新成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.patch("/item/{product_id:int}/view", summary="增加产品浏览次数")
async def increment_product_view(
        product_id: int
        # current_user_id: int = Depends(get_current_user_id)  # 临时注释认证，用于测试
):
    """
    增加产品浏览次数

    Args:
        product_id: 产品ID
        current_user_id: 当前用户ID

    Returns:
        更新后的产品信息
    """
    try:
        updated_product = await ProductService.increment_view_count(product_id)
        if not updated_product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)
        if hasattr(updated_product, 'to_dict'):
            product_dict = await updated_product.to_dict()
        elif hasattr(updated_product, 'dict'):
            product_dict = updated_product.dict()
        else:
            product_dict = dict(updated_product)
        return SuccessResponse(data=product_dict, msg="浏览次数更新成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/categories/list", summary="获取所有产品分类")
async def get_product_categories():
    """
    获取所有产品分类

    Returns:
        产品分类列表
    """
    try:
        categories = await ProductService.get_product_categories()
        return SuccessResponse(data={"categories": categories}, msg="获取分类成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/materials/available", summary="获取可关联的成品物料列表")
async def get_available_materials(
    keyword: Optional[str] = Query(None, description="物料编码/名称关键词"),
    include_linked: bool = Query(False, description="是否包含已关联产品的物料")
):
    """
    获取可关联的成品物料列表（用于库存商品创建时选取物料）

    Args:
        keyword: 物料编码/名称关键词(模糊搜索)
        include_linked: 是否包含已关联产品的物料(编辑场景)

    Returns:
        成品物料列表
    """
    try:
        materials = await ProductService.get_available_materials(
            keyword=keyword,
            include_linked=include_linked
        )
        return SuccessResponse(data={"items": materials, "total": len(materials)}, msg="获取物料列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


# ==================== 库存关联接口 ====================

try:
    from base.plugins.inventory.services.inventory_service import QuantService
    INVENTORY_AVAILABLE = True
except ImportError:
    QuantService = None
    INVENTORY_AVAILABLE = False


@product_router.get("/item/{product_id:int}/inventory", summary="获取产品库存详情")
async def get_product_inventory(
        product_id: int
):
    """
    获取产品的库存详情

    Args:
        product_id: 产品ID

    Returns:
        产品库存信息（按库位分组）
    """
    try:
        if not INVENTORY_AVAILABLE or QuantService is None:
            return ErrorResponse(msg="库存模块未启用", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        product = await ProductService.get_by_id(product_id)
        if not product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)

        quants = await QuantService.get_by_product(product.name)
        
        inventory_data = {
            "product_id": product.id,
            "product_name": product.name,
            "total_quantity": 0,
            "total_reserved": 0,
            "total_available": 0,
            "locations": []
        }

        location_map = {}
        for quant in quants:
            loc_key = quant.location_id
            if loc_key not in location_map:
                location_map[loc_key] = {
                    "location_id": quant.location_id,
                    "location_code": quant.location_code,
                    "location_name": quant.location_name,
                    "quantity": 0,
                    "reserved_quantity": 0,
                    "available_quantity": 0,
                    "lots": []
                }
            
            location_map[loc_key]["quantity"] += float(quant.quantity) if quant.quantity else 0
            location_map[loc_key]["reserved_quantity"] += float(quant.reserved_quantity) if quant.reserved_quantity else 0
            location_map[loc_key]["available_quantity"] += float(quant.available_quantity) if quant.available_quantity else 0
            
            if quant.lot_name:
                location_map[loc_key]["lots"].append({
                    "lot_id": quant.lot_id,
                    "lot_name": quant.lot_name,
                    "quantity": float(quant.quantity) if quant.quantity else 0,
                    "expiry_date": quant.expiry_date.strftime("%Y-%m-%d") if quant.expiry_date else None
                })

        inventory_data["locations"] = list(location_map.values())
        inventory_data["total_quantity"] = sum(loc["quantity"] for loc in inventory_data["locations"])
        inventory_data["total_reserved"] = sum(loc["reserved_quantity"] for loc in inventory_data["locations"])
        inventory_data["total_available"] = sum(loc["available_quantity"] for loc in inventory_data["locations"])

        return SuccessResponse(data=inventory_data, msg="获取库存成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/inventory/list", summary="批量获取产品库存")
async def get_product_inventory_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量")
):
    """
    批量获取产品库存信息

    Args:
        page: 页码
        page_size: 每页数量

    Returns:
        产品库存列表
    """
    try:
        if not INVENTORY_AVAILABLE or QuantService is None:
            return ErrorResponse(msg="库存模块未启用", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        quants, total = await QuantService.get_list(page=page, page_size=page_size)
        
        product_map = {}
        for quant in quants:
            prod_key = quant.product_code
            if prod_key not in product_map:
                product_map[prod_key] = {
                    "product_code": quant.product_code,
                    "product_name": quant.product_name,
                    "total_quantity": 0,
                    "total_reserved": 0,
                    "total_available": 0
                }
            
            product_map[prod_key]["total_quantity"] += float(quant.quantity) if quant.quantity else 0
            product_map[prod_key]["total_reserved"] += float(quant.reserved_quantity) if quant.reserved_quantity else 0
            product_map[prod_key]["total_available"] += float(quant.available_quantity) if quant.available_quantity else 0

        inventory_list = list(product_map.values())

        response_data = {
            "total": len(inventory_list),
            "page": page,
            "page_size": page_size,
            "items": inventory_list
        }

        return SuccessResponse(data=response_data, msg="获取库存列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


# ==================== BOM关联接口 ====================

try:
    from base.plugins.mes.services.base_data_service import BomService
    MES_AVAILABLE = True
except ImportError:
    BomService = None
    MES_AVAILABLE = False


@product_router.get("/item/{product_id:int}/bom", summary="获取产品BOM结构")
async def get_product_bom(
        product_id: int,
        version: Optional[str] = Query(None, description="BOM版本号"),
        expand_level: int = Query(1, ge=1, le=10, description="展开层级")
):
    """
    获取产品的BOM结构（物料清单）

    Args:
        product_id: 产品ID
        version: BOM版本号（可选）
        expand_level: 展开层级（1=单层，>1=多级展开）

    Returns:
        产品BOM结构（支持多级展开）
    """
    try:
        if not MES_AVAILABLE or BomService is None:
            return ErrorResponse(msg="MES模块未启用", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        product = await ProductService.get_by_id(product_id)
        if not product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)

        # 根据展开层级选择查询方式
        if expand_level == 1:
            boms = await BomService.get_bom_by_product(product.name, version)
            bom_data = {
                "product_id": product.id,
                "product_name": product.name,
                "version": version or "latest",
                "expand_level": 1,
                "total_items": len(boms),
                "items": []
            }

            for bom in boms:
                item_info = {
                    "id": bom.id,
                    "product_code": bom.product_code,
                    "product_name": bom.product_name,
                    "version": bom.version,
                    "level": bom.level,
                    "parent_item_code": bom.parent_item_code,
                    "item_id": bom.item_id,
                    "item_code": bom.item_code,
                    "item_name": bom.item_name,
                    "quantity": float(bom.quantity) if bom.quantity and hasattr(bom.quantity, "__float__") else bom.quantity,
                    "unit": bom.unit,
                    "scrap_rate": float(bom.scrap_rate) if bom.scrap_rate and hasattr(bom.scrap_rate, "__float__") else bom.scrap_rate,
                    "remark": bom.remark,
                    "is_active": bom.is_active,
                }
                
                if bom.item_id:
                    item_product = await ProductService.get_by_id(bom.item_id)
                    if item_product:
                        item_info["item_product_info"] = {
                            "id": item_product.id,
                            "name": item_product.name,
                            "description": item_product.description,
                            "price": float(item_product.price) if item_product.price and hasattr(item_product.price, "__float__") else item_product.price,
                            "category": item_product.category,
                        }
                
                bom_data["items"].append(item_info)

        else:
            # 多级展开
            multi_level_bom = await BomService.get_multi_level_bom(
                product_code=product.name,
                version=version,
                max_level=expand_level
            )
            
            bom_data = {
                "product_id": product.id,
                "product_name": product.name,
                "version": version or "latest",
                "expand_level": expand_level,
                "total_items": len(multi_level_bom),
                "items": multi_level_bom
            }

        return SuccessResponse(data=bom_data, msg="获取BOM成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/bom/list", summary="获取所有BOM列表")
async def get_product_bom_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量"),
        product_code: Optional[str] = Query(None, description="成品编码")
):
    """
    获取所有BOM列表

    Args:
        page: 页码
        page_size: 每页数量
        product_code: 成品编码（可选）

    Returns:
        BOM列表
    """
    try:
        if not MES_AVAILABLE or BomService is None:
            return ErrorResponse(msg="MES模块未启用", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        boms, total = await BomService.get_list(page=page, page_size=page_size, product_code=product_code)
        
        bom_list = []
        for bom in boms:
            item_info = {
                "id": bom.id,
                "product_id": bom.product_id,
                "product_code": bom.product_code,
                "product_name": bom.product_name,
                "version": bom.version,
                "level": bom.level,
                "parent_item_code": bom.parent_item_code,
                "item_id": bom.item_id,
                "item_code": bom.item_code,
                "item_name": bom.item_name,
                "quantity": float(bom.quantity) if bom.quantity and hasattr(bom.quantity, "__float__") else bom.quantity,
                "unit": bom.unit,
                "scrap_rate": float(bom.scrap_rate) if bom.scrap_rate and hasattr(bom.scrap_rate, "__float__") else bom.scrap_rate,
                "remark": bom.remark,
                "is_active": bom.is_active,
            }
            bom_list.append(item_info)

        response_data = {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": bom_list
        }

        return SuccessResponse(data=response_data, msg="获取BOM列表成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)


@product_router.get("/item/{product_id:int}/mrp", summary="计算物料需求计划(MRP)")
async def calculate_mrp(
        product_id: int,
        quantity: Decimal = Query(..., ge=Decimal("0.000001"), description="需求数量"),
        version: Optional[str] = Query(None, description="BOM版本号"),
        max_level: int = Query(5, ge=1, le=10, description="最大展开层级")
):
    """
    计算产品的物料需求计划(MRP)
    
    根据需求数量，递归计算所需的所有物料及其数量（考虑损耗率）

    Args:
        product_id: 产品ID
        quantity: 需求数量
        version: BOM版本号（可选）
        max_level: 最大展开层级

    Returns:
        MRP计算结果，包含详细BOM和物料汇总
    """
    try:
        if not MES_AVAILABLE or BomService is None:
            return ErrorResponse(msg="MES模块未启用", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        product = await ProductService.get_by_id(product_id)
        if not product:
            return ErrorResponse(msg="产品不存在", status_code=status.HTTP_404_NOT_FOUND)

        mrp_result = await BomService.calculate_mrp(
            product_code=product.name,
            demand_quantity=quantity,
            version=version,
            max_level=max_level
        )

        mrp_result["product_id"] = product.id
        mrp_result["product_name"] = product.name

        return SuccessResponse(data=mrp_result, msg="MRP计算成功")
    except Exception as e:
        return ErrorResponse(msg=str(e), status_code=status.HTTP_400_BAD_REQUEST)