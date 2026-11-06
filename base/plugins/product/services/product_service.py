"""
产品服务层
"""
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from decimal import Decimal
from tortoise.expressions import Q

# 尝试导入依赖项
try:
    from base.plugins.product.models.product import Product
    from base.plugins.product.schemas.product_schema import ProductCreate, ProductUpdate
    from base.common.security import get_password_hash, verify_password
except ImportError:
    # 定义临时依赖，以便在没有base模块的情况下也能工作
    from typing import Any
    from datetime import datetime
    from decimal import Decimal

    class Product:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        @classmethod
        async def create(cls, **kwargs):
            instance = cls(**kwargs)
            instance.id = 1  # 模拟ID
            instance.created_at = datetime.now()
            instance.updated_at = datetime.now()
            instance.is_active = True
            instance.is_hot = False
            instance.is_new = False
            instance.view_count = 0
            instance.sales_count = 0
            instance.stock = 0
            return instance

        @classmethod
        async def filter(cls, **kwargs):
            # 模拟过滤
            class MockQuerySet:
                async def first(self):
                    return None

                async def exists(self):
                    return False

                async def delete(self):
                    return 0

                async def count(self):
                    return 0

                async def offset(self, offset):
                    return self

                async def limit(self, limit):
                    return self

                async def order_by(self, order):
                    return self

                def filter(self, **kwargs):
                    return self

                def exclude(self, **kwargs):
                    return self

                def all(self):
                    return self

            return MockQuerySet()

        @classmethod
        async def all(cls):
            return await cls.filter()

        async def update_from_dict(self, data):
            for key, value in data.items():
                setattr(self, key, value)
            self.updated_at = datetime.now()
            return self

        async def save(self):
            pass

    class ProductCreate:
        def __init__(self, name, price, original_price=None, **kwargs):
            self.name = name
            self.price = price
            self.original_price = original_price
            for key, value in kwargs.items():
                setattr(self, key, value)

    class ProductUpdate:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self, exclude_unset=False):
            return {k: v for k, v in self.__dict__.items() if v is not None}


class ProductService:
    model = "product"
    """产品服务类"""

    @staticmethod
    async def get_by_id(product_id: int) -> Optional[Product]:
        """
        根据ID获取产品

        Args:
            product_id: 产品ID

        Returns:
            Optional[Product]: 产品对象,不存在返回None
        """
        return await Product.filter(id=product_id).first()

    @staticmethod
    async def get_by_name(name: str) -> Optional[Product]:
        """
        根据名称获取产品

        Args:
            name: 产品名称

        Returns:
            Optional[Product]: 产品对象,不存在返回None
        """
        return await Product.filter(name=name).first()

    @staticmethod
    async def create_product(product_data: ProductCreate) -> Product:
        """
        创建新产品

        Args:
            product_data: 产品创建数据
                - is_stock_item=True 且 material_id 有值：从物料表选取成品物料，自动填充信息
                - is_stock_item=True 且 material_id 为空：直接创建（需手动填写信息）
                - is_stock_item=False：虚拟商品，直接创建

        Returns:
            Product: 创建的产品对象

        Raises:
            ValueError: 产品名称已存在 / 物料不存在 / 物料非成品类型 / 物料已关联产品
        """
        material = None
        if product_data.is_stock_item and product_data.material_id:
            from base.plugins.mes.models.base_data import Material
            material = await Material.get_or_none(id=product_data.material_id)
            if not material:
                raise ValueError("关联的物料不存在")
            if material.material_type != "finished":
                raise ValueError("只能关联成品类型的物料")
            if material.product_id is not None:
                raise ValueError("该物料已关联其他产品")

        # 如果关联了物料，从物料表获取产品编码和名称（以物料表为准）
        product_code = product_data.product_code
        product_name = product_data.name
        product_desc = product_data.description
        if material:
            product_code = material.material_code
            product_name = material.material_name
            if not product_data.description:
                product_desc = f"规格: {material.specification or '-'}，单位: {material.unit or '-'}"

        # 检查产品名称是否已存在
        if await ProductService.check_name_exists(product_name):
            raise ValueError("产品名称已存在")

        # 如果关联了物料，检查产品编码是否重复
        if material and product_code:
            existing_by_code = await Product.filter(product_code=product_code).first()
            if existing_by_code:
                raise ValueError("产品编码已存在")

        # 创建产品
        product = await Product.create(
            product_code=product_code,
            name=product_name,
            description=product_desc,
            price=product_data.price,
            original_price=product_data.original_price,
            stock=product_data.stock or 0,
            category=product_data.category,
            tags=product_data.tags,
            images=product_data.images,
            is_active=product_data.is_active,
            is_hot=product_data.is_hot,
            is_new=product_data.is_new,
            is_stock_item=product_data.is_stock_item,
            recharge_hours=product_data.recharge_hours,
            bonus_hours=product_data.bonus_hours,
            discount_description=product_data.discount_description,
            sort=product_data.sort,
        )

        # 建立物料与产品的关联
        if material:
            material.product_id = product.id
            await material.save()

        return product

    @staticmethod
    async def update_product(product_id: int, product_data: ProductUpdate) -> Optional[Product]:
        """
        更新产品信息

        Args:
            product_id: 产品ID
            product_data: 更新数据

        Returns:
            Optional[Product]: 更新后的产品对象

        Raises:
            ValueError: 产品名称已被其他产品使用
        """
        product = await Product.filter(id=product_id).first()
        if not product:
            return None

        # 检查产品名称是否被其他产品使用
        if product_data.name and product_data.name != product.name:
            if await ProductService.check_name_exists(product_data.name, exclude_id=product_id):
                raise ValueError("产品名称已被使用")

        # 只更新非None的字段
        update_data = product_data.model_dump(exclude_none=True)
        print(f"[ProductService.update_product] product_id={product_id}")
        print(f"[ProductService.update_product] update_data={update_data}")
        await product.update_from_dict(update_data).save()

        return product

    @staticmethod
    async def delete_product(product_id: int) -> bool:
        """
        删除产品

        Args:
            product_id: 产品ID

        Returns:
            bool: 是否删除成功
        """
        deleted_count = await Product.filter(id=product_id).delete()
        return deleted_count > 0

    @staticmethod
    async def toggle_product_status(product_id: int) -> Optional[Product]:
        """
        切换产品上架状态

        Args:
            product_id: 产品ID

        Returns:
            Optional[Product]: 更新后的产品对象
        """
        product = await Product.filter(id=product_id).first()
        if not product:
            return None

        # 切换状态
        product.is_active = not product.is_active
        await product.save()

        return product

    @staticmethod
    async def update_stock(product_id: int, quantity: int) -> Optional[Product]:
        """
        更新产品库存

        Args:
            product_id: 产品ID
            quantity: 库存变更数量（正数增加，负数减少）

        Returns:
            Optional[Product]: 更新后的产品对象

        Raises:
            ValueError: 库存不足
        """
        product = await Product.filter(id=product_id).first()
        if not product:
            return None

        # 检查库存是否足够
        if product.stock + quantity < 0:
            raise ValueError("库存不足")

        # 更新库存
        product.stock += quantity
        await product.save()

        return product

    @staticmethod
    async def update_sales_count(product_id: int, quantity: int) -> Optional[Product]:
        """
        更新产品销售数量

        Args:
            product_id: 产品ID
            quantity: 销售数量增加量

        Returns:
            Optional[Product]: 更新后的产品对象
        """
        product = await Product.filter(id=product_id).first()
        if not product:
            return None

        # 更新销售数量
        product.sales_count += quantity
        await product.save()

        return product

    @staticmethod
    async def increment_view_count(product_id: int) -> Optional[Product]:
        """
        增加产品浏览次数

        Args:
            product_id: 产品ID

        Returns:
            Optional[Product]: 更新后的产品对象
        """
        product = await Product.filter(id=product_id).first()
        if not product:
            return None

        # 增加浏览次数
        product.view_count += 1
        await product.save()

        return product

    @staticmethod
    async def get_product_list(
            page: int = 1,
            page_size: int = 10,
            name: Optional[str] = None,
            category: Optional[str] = None,
            is_active: Optional[bool] = None,
            is_hot: Optional[bool] = None,
            is_new: Optional[bool] = None,
            is_stock_item: Optional[bool] = None,
    ) -> Tuple[List[Product], int]:
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
            Tuple[List[Product], int]: (产品列表, 总数)
        """
        query = Product.all()

        # 构建查询条件
        if name:
            query = query.filter(name__icontains=name)
        if category:
            query = query.filter(category=category)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        if is_hot is not None:
            query = query.filter(is_hot=is_hot)
        if is_new is not None:
            query = query.filter(is_new=is_new)
        if is_stock_item is not None:
            query = query.filter(is_stock_item=is_stock_item)

        # 获取总数
        total = await query.count()

        # 分页查询
        offset = (page - 1) * page_size
        products = await query.offset(offset).limit(page_size).order_by('-created_at')

        return products, total

    @staticmethod
    async def get_product_categories() -> List[str]:
        """
        获取所有产品分类

        Returns:
            List[str]: 分类列表
        """
        # 获取所有不重复的分类
        categories = await Product.filter(category__not_isnull=True).distinct().values_list('category', flat=True)
        return categories

    @staticmethod
    async def check_name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
        """
        检查产品名称是否存在

        Args:
            name: 产品名称
            exclude_id: 排除的产品ID(用于更新时检查)

        Returns:
            bool: 是否存在
        """
        query = Product.filter(name=name)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def get_available_materials(
        keyword: Optional[str] = None,
        include_linked: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取可关联的成品物料列表

        Args:
            keyword: 物料编码/名称关键词(模糊搜索)
            include_linked: 是否包含已关联产品的物料(编辑场景)

        Returns:
            List[Dict]: 成品物料列表
        """
        from base.plugins.mes.models.base_data import Material

        query = Material.filter(material_type="finished", is_active=True)
        if not include_linked:
            query = query.filter(product_id__isnull=True)
        if keyword:
            query = query.filter(
                Q(material_code__icontains=keyword) | Q(material_name__icontains=keyword)
            )

        materials = await query.order_by("material_code").limit(50)
        result = []
        for m in materials:
            result.append({
                "id": m.id,
                "material_code": m.material_code,
                "material_name": m.material_name,
                "specification": m.specification,
                "unit": m.unit,
                "product_id": m.product_id,
                "initial_stock": m.initial_stock or 0,
            })
        return result


class CategoryService:
    """产品分类服务"""

    @staticmethod
    async def create_category(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建产品分类

        Args:
            data: 分类数据

        Returns:
            创建的分类
        """
        from base.plugins.product.models.product import ProductCategory

        if await ProductCategory.filter(name=data['name']).exists():
            raise ValueError("分类名称已存在")

        if data.get('code') and await ProductCategory.filter(code=data['code']).exists():
            raise ValueError("分类编码已存在")

        category = await ProductCategory.create(**data)
        return await category.to_dict()

    @staticmethod
    async def get_category_by_id(category_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取分类

        Args:
            category_id: 分类ID

        Returns:
            分类信息
        """
        from base.plugins.product.models.product import ProductCategory

        category = await ProductCategory.get_or_none(id=category_id)
        if category:
            return await category.to_dict()
        return None

    @staticmethod
    async def update_category(category_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        更新分类

        Args:
            category_id: 分类ID
            data: 更新数据

        Returns:
            更新后的分类
        """
        from base.plugins.product.models.product import ProductCategory

        category = await ProductCategory.get_or_none(id=category_id)
        if not category:
            return None

        if 'name' in data and data['name'] != category.name:
            if await ProductCategory.filter(name=data['name']).exists():
                raise ValueError("分类名称已存在")

        if 'code' in data and data['code'] != category.code:
            if data['code'] and await ProductCategory.filter(code=data['code']).exists():
                raise ValueError("分类编码已存在")

        for key, value in data.items():
            setattr(category, key, value)

        await category.save()
        return await category.to_dict()

    @staticmethod
    async def delete_category(category_id: int) -> bool:
        """
        删除分类

        Args:
            category_id: 分类ID

        Returns:
            是否删除成功
        """
        from base.plugins.product.models.product import ProductCategory
        from base.plugins.product.models.product import Product

        if await Product.filter(category=category_id).exists():
            raise ValueError("该分类下存在产品，无法删除")

        deleted_count = await ProductCategory.filter(id=category_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_category_list(
        page: int = 1,
        page_size: int = 10,
        name: Optional[str] = None,
        parent_id: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取分类列表

        Args:
            page: 页码
            page_size: 每页数量
            name: 分类名称关键词
            parent_id: 父分类ID
            is_active: 是否启用

        Returns:
            分类列表和总数
        """
        from base.plugins.product.models.product import ProductCategory

        query = ProductCategory.all()

        if name:
            query = query.filter(name__icontains=name)
        if parent_id is not None:
            query = query.filter(parent_id=parent_id)
        if is_active is not None:
            query = query.filter(is_active=is_active)

        query = query.order_by("sort", "id")

        total = await query.count()
        items = await query.offset((page - 1) * page_size).limit(page_size)

        result = []
        for item in items:
            result.append(await item.to_dict())

        return result, total

    @staticmethod
    async def get_category_options() -> List[Dict[str, Any]]:
        """
        获取分类选项列表（用于下拉选择）

        Returns:
            分类选项列表
        """
        from base.plugins.product.models.product import ProductCategory

        categories = await ProductCategory.filter(is_active=True).order_by("sort", "id")
        return [{"value": cat.name, "label": cat.name} for cat in categories]
