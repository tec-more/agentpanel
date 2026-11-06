"""
产品属性与变体服务层
"""
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

try:
    from tortoise.expressions import Q
    from base.plugins.product.models.attribute import Attribute, AttributeValue
    from base.plugins.product.models.product import ProductVariant
    from base.plugins.mes.models.base_data import MaterialVariant
except ImportError:
    Q = None
    pass


class AttributeService:
    """属性服务"""

    @staticmethod
    async def create_attribute(data: Dict[str, Any]) -> Dict[str, Any]:
        if await Attribute.filter(name=data['name']).exists():
            raise ValueError("属性名称已存在")
        if await Attribute.filter(code=data['code']).exists():
            raise ValueError("属性编码已存在")
        attr = await Attribute.create(**data)
        return await attr.to_dict()

    @staticmethod
    async def get_attribute_by_id(attr_id: int) -> Optional[Dict[str, Any]]:
        attr = await Attribute.get_or_none(id=attr_id)
        return await attr.to_dict() if attr else None

    @staticmethod
    async def update_attribute(attr_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        attr = await Attribute.get_or_none(id=attr_id)
        if not attr:
            return None
        if 'name' in data and data['name'] != attr.name:
            if await Attribute.filter(name=data['name']).exists():
                raise ValueError("属性名称已存在")
        if 'code' in data and data['code'] != attr.code:
            if await Attribute.filter(code=data['code']).exists():
                raise ValueError("属性编码已存在")
        for key, value in data.items():
            setattr(attr, key, value)
        await attr.save()
        return await attr.to_dict()

    @staticmethod
    async def delete_attribute(attr_id: int) -> bool:
        deleted_count = await Attribute.filter(id=attr_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_attribute_list(
        page: int = 1,
        page_size: int = 10,
        name: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = Attribute.all()
        if name:
            query = query.filter(name__icontains=name)
        if category:
            query = query.filter(category=category)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        query = query.order_by("sort", "id")
        total = await query.count()
        items = await query.offset((page - 1) * page_size).limit(page_size)
        return [await item.to_dict() for item in items], total

    @staticmethod
    async def get_attribute_options(category: Optional[str] = None) -> List[Dict[str, Any]]:
        query = Attribute.filter(is_active=True)
        if category:
            query = query.filter(Q(category=category) | Q(category="both"))
        else:
            query = query.filter(category="both")
        attrs = await query.order_by("sort", "id")
        return [{"value": attr.code, "label": attr.name} for attr in attrs]


class AttributeValueService:
    """属性值服务"""

    @staticmethod
    async def create_attribute_value(data: Dict[str, Any]) -> Dict[str, Any]:
        category_id = data.get('product_category_id')
        filters = {'attribute_id': data['attribute_id'], 'value': data['value']}
        if category_id is not None:
            filters['product_category_id'] = category_id
        else:
            filters['product_category_id__isnull'] = True
        if await AttributeValue.filter(**filters).exists():
            raise ValueError("该属性值已存在")
        value = await AttributeValue.create(**data)
        return await value.to_dict()

    @staticmethod
    async def get_attribute_value_by_id(value_id: int) -> Optional[Dict[str, Any]]:
        value = await AttributeValue.get_or_none(id=value_id)
        return await value.to_dict() if value else None

    @staticmethod
    async def update_attribute_value(value_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        value = await AttributeValue.get_or_none(id=value_id)
        if not value:
            return None
        if 'value' in data and data['value'] != value.value:
            if await AttributeValue.filter(attribute_id=value.attribute_id, value=data['value']).exists():
                raise ValueError("该属性值已存在")
        for key, value in data.items():
            setattr(value, key, value)
        await value.save()
        return await value.to_dict()

    @staticmethod
    async def delete_attribute_value(value_id: int) -> bool:
        deleted_count = await AttributeValue.filter(id=value_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_attribute_values(attribute_id: int, product_category_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = AttributeValue.filter(attribute_id=attribute_id)
        if product_category_id is not None:
            query = query.filter(Q(product_category_id=product_category_id) | Q(product_category_id__isnull=True))
        values = await query.order_by("sort")
        return [await v.to_dict() for v in values]


class MaterialVariantService:
    """物料变体服务"""

    @staticmethod
    async def create_material_variant(data: Dict[str, Any]) -> Dict[str, Any]:
        if await MaterialVariant.filter(variant_code=data['variant_code']).exists():
            raise ValueError("变体编码已存在")
        variant = await MaterialVariant.create(**data)
        return await variant.to_dict()

    @staticmethod
    async def get_material_variant_by_id(variant_id: int) -> Optional[Dict[str, Any]]:
        variant = await MaterialVariant.get_or_none(id=variant_id)
        return await variant.to_dict() if variant else None

    @staticmethod
    async def update_material_variant(variant_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        variant = await MaterialVariant.get_or_none(id=variant_id)
        if not variant:
            return None
        if 'variant_code' in data and data['variant_code'] != variant.variant_code:
            if await MaterialVariant.filter(variant_code=data['variant_code']).exists():
                raise ValueError("变体编码已存在")
        for key, value in data.items():
            setattr(variant, key, value)
        await variant.save()
        return await variant.to_dict()

    @staticmethod
    async def delete_material_variant(variant_id: int) -> bool:
        deleted_count = await MaterialVariant.filter(id=variant_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_material_variant_list(
        page: int = 1,
        page_size: int = 10,
        material_id: Optional[int] = None,
        variant_code: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = MaterialVariant.all()
        if material_id:
            query = query.filter(material_id=material_id)
        if variant_code:
            query = query.filter(variant_code__icontains=variant_code)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        query = query.order_by("id")
        total = await query.count()
        items = await query.offset((page - 1) * page_size).limit(page_size)
        return [await item.to_dict() for item in items], total


class ProductVariantService:
    """产品变体服务"""

    @staticmethod
    async def create_product_variant(data: Dict[str, Any]) -> Dict[str, Any]:
        if await ProductVariant.filter(sku=data['sku']).exists():
            raise ValueError("SKU已存在")
        variant = await ProductVariant.create(**data)
        return await variant.to_dict()

    @staticmethod
    async def get_product_variant_by_id(variant_id: int) -> Optional[Dict[str, Any]]:
        variant = await ProductVariant.get_or_none(id=variant_id)
        return await variant.to_dict() if variant else None

    @staticmethod
    async def update_product_variant(variant_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        variant = await ProductVariant.get_or_none(id=variant_id)
        if not variant:
            return None
        if 'sku' in data and data['sku'] != variant.sku:
            if await ProductVariant.filter(sku=data['sku']).exists():
                raise ValueError("SKU已存在")
        for key, value in data.items():
            setattr(variant, key, value)
        await variant.save()
        return await variant.to_dict()

    @staticmethod
    async def delete_product_variant(variant_id: int) -> bool:
        deleted_count = await ProductVariant.filter(id=variant_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_product_variant_list(
        page: int = 1,
        page_size: int = 10,
        product_id: Optional[int] = None,
        sku: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = ProductVariant.all()
        if product_id:
            query = query.filter(product_id=product_id)
        if sku:
            query = query.filter(sku__icontains=sku)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        query = query.order_by("id")
        total = await query.count()
        items = await query.offset((page - 1) * page_size).limit(page_size)
        return [await item.to_dict() for item in items], total