"""
库存管理模块 Service层实现
基于Odoo风格实现完整的业务逻辑
"""
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid
try:
    from tortoise import connections
    from tortoise.functions import Sum
    from base.plugins.inventory.models.inventory_models import (
        StockLocation, StockWarehouse, StockPickingType, StockPicking, StockMove,
        StockMoveLine, StockQuant, StockQuantReservation,
        StockLot, StockPackage
    )
    from base.plugins.inventory.schemas.inventory_schema import (
        StockLocationCreate, StockLocationUpdate,
        StockWarehouseCreate, StockWarehouseUpdate,
        StockPickingTypeCreate, StockPickingTypeUpdate,
        StockPickingCreate, StockPickingUpdate,
        StockMoveCreate, StockMoveUpdate,
        StockMoveLineCreate, StockMoveLineUpdate,
        StockQuantCreate, StockQuantUpdate,
        StockQuantReservationCreate,
        StockLotCreate, StockLotUpdate,
        StockPackageCreate, StockPackageUpdate,
    )
    try:
        from base.plugins.product.models.product import Product
        PRODUCT_AVAILABLE = True
    except ImportError:
        Product = None
        PRODUCT_AVAILABLE = False
except ImportError:
    # Mock classes for standalone testing
    from datetime import datetime
    from decimal import Decimal

    class BaseModelMock:
        id = 1
        created_at = datetime.now()
        updated_at = datetime.now()

        async def save(self):
            pass

        async def delete(self):
            pass

        async def update_from_dict(self, data):
            for key, value in data.items():
                setattr(self, key, value)
            return self

        @classmethod
        async def create(cls, **kwargs):
            obj = cls()
            for key, value in kwargs.items():
                setattr(obj, key, value)
            return obj

        @classmethod
        async def filter(cls, **kwargs):
            class MockQuerySet:
                async def first(self): return None
                async def exists(self): return False
                async def delete(self): return 0
                async def count(self): return 0
                async def offset(self, n): return self
                async def limit(self, n): return self
                async def order_by(self, order): return self
                def filter(self, **kwargs): return self
                def exclude(self, **kwargs): return self
                def all(self): return []
                async def values_list(self, field, flat=False): return []
                async def aggregate(self, *args): return {}
            return MockQuerySet()

        async def to_dict(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    class StockLocation(BaseModelMock): pass
    class StockWarehouse(BaseModelMock): pass
    class StockPickingType(BaseModelMock): pass
    class StockPicking(BaseModelMock): pass
    class StockMove(BaseModelMock): pass
    class StockMoveLine(BaseModelMock): pass
    class StockQuant(BaseModelMock): pass
    class StockQuantReservation(BaseModelMock): pass
    class StockLot(BaseModelMock): pass
    class StockPackage(BaseModelMock): pass

    class StockLocationCreate:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class StockLocationUpdate(StockLocationCreate):
        def model_dump(self, exclude_none=False):
            return {k: v for k, v in self.__dict__.items() if v is not None}

    class StockWarehouseCreate(StockLocationCreate): pass
    class StockWarehouseUpdate(StockLocationUpdate): pass
    class StockPickingTypeCreate(StockLocationCreate): pass
    class StockPickingTypeUpdate(StockLocationUpdate): pass
    class StockPickingCreate(StockLocationCreate): pass
    class StockPickingUpdate(StockLocationUpdate): pass
    class StockMoveCreate(StockLocationCreate): pass
    class StockMoveUpdate(StockLocationUpdate): pass
    class StockMoveLineCreate(StockLocationCreate): pass
    class StockMoveLineUpdate(StockLocationUpdate): pass
    class StockQuantCreate(StockLocationCreate): pass
    class StockQuantUpdate(StockLocationUpdate): pass
    class StockQuantReservationCreate(StockLocationCreate): pass
    class StockLotCreate(StockLocationCreate): pass
    class StockLotUpdate(StockLocationUpdate): pass
    class StockPackageCreate(StockLocationCreate): pass
    class StockPackageUpdate(StockLocationUpdate): pass
    Product = None
    PRODUCT_AVAILABLE = False


# ==================== 产品查询辅助函数 ====================

async def get_product_by_code(product_code: str) -> Optional[dict]:
    """根据产品编码查询产品信息"""
    if not PRODUCT_AVAILABLE or Product is None:
        return None
    
    try:
        product = await Product.filter(name=product_code).first()
        if product:
            return {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': float(product.price) if hasattr(product.price, '__float__') else product.price,
                'uom_code': getattr(product, 'uom_code', 'unit'),
                'uom_name': getattr(product, 'uom_name', '件'),
                'secondary_uom_code': getattr(product, 'secondary_uom_code', None),
                'secondary_uom_name': getattr(product, 'secondary_uom_name', None),
                'conversion_factor': float(getattr(product, 'conversion_factor', 1)) if hasattr(getattr(product, 'conversion_factor', 1), '__float__') else 1,
            }
    except Exception:
        pass
    
    return None


async def get_product_by_name(product_name: str) -> Optional[dict]:
    """根据产品名称查询产品信息"""
    if not PRODUCT_AVAILABLE or Product is None:
        return None
    
    try:
        product = await Product.filter(name=product_name).first()
        if product:
            return {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': float(product.price) if hasattr(product.price, '__float__') else product.price,
                'uom_code': getattr(product, 'uom_code', 'unit'),
                'uom_name': getattr(product, 'uom_name', '件'),
                'secondary_uom_code': getattr(product, 'secondary_uom_code', None),
                'secondary_uom_name': getattr(product, 'secondary_uom_name', None),
                'conversion_factor': float(getattr(product, 'conversion_factor', 1)) if hasattr(getattr(product, 'conversion_factor', 1), '__float__') else 1,
            }
    except Exception:
        pass
    
    return None


# ==================== 单位转换工具 ====================

class UomConverter:
    """单位转换工具类"""
    
    @staticmethod
    def to_secondary(uom_qty: Decimal, conversion_factor: Decimal) -> Decimal:
        """主单位转辅助单位
        
        Args:
            uom_qty: 主单位数量
            conversion_factor: 换算比例（主单位 = 辅助单位 × 换算比例）
        
        Returns:
            辅助单位数量
        """
        if conversion_factor == 0:
            return Decimal("0")
        return uom_qty / conversion_factor
    
    @staticmethod
    def to_uom(secondary_qty: Decimal, conversion_factor: Decimal) -> Decimal:
        """辅助单位转主单位
        
        Args:
            secondary_qty: 辅助单位数量
            conversion_factor: 换算比例（主单位 = 辅助单位 × 换算比例）
        
        Returns:
            主单位数量
        """
        return secondary_qty * conversion_factor
    
    @staticmethod
    async def get_product_uom_info(product_code: str) -> Optional[dict]:
        """获取产品的单位信息"""
        if not PRODUCT_AVAILABLE or Product is None:
            return None
        
        try:
            product = await Product.filter(name=product_code).first()
            if product:
                return {
                    'uom_id': getattr(product, 'uom_id', None),
                    'uom_code': getattr(product, 'uom_code', 'unit'),
                    'uom_name': getattr(product, 'uom_name', '件'),
                    'uom_category': getattr(product, 'uom_category', 'unit'),
                    'secondary_uom_id': getattr(product, 'secondary_uom_id', None),
                    'secondary_uom_code': getattr(product, 'secondary_uom_code', None),
                    'secondary_uom_name': getattr(product, 'secondary_uom_name', None),
                    'conversion_factor': float(getattr(product, 'conversion_factor', 1)) if hasattr(getattr(product, 'conversion_factor', 1), '__float__') else 1,
                }
        except Exception:
            pass
        
        return None


# ==================== 序列码生成工具 ====================

class SequenceGenerator:
    """序列码生成器 - 支持Odoo风格的序列码模板"""

    @staticmethod
    def generate_sequence_code(template: str, picking_type_code: str, last_sequence: int) -> str:
        """
        根据模板生成序列码
        支持变量：{type}/{year}/{month}/{day}/{sequence}
        """
        now = datetime.now()
        # 替换变量
        sequence_code = template.replace("{type}", picking_type_code)
        sequence_code = sequence_code.replace("{year}", str(now.year))
        sequence_code = sequence_code.replace("{month}", str(now.month).zfill(2))
        sequence_code = sequence_code.replace("{day}", str(now.day).zfill(2))
        sequence_code = sequence_code.replace("{sequence}", str(last_sequence + 1).zfill(5))

        return sequence_code

    @staticmethod
    def generate_code(prefix: str = "", use_uuid: bool = False) -> str:
        """生成通用编码"""
        if use_uuid:
            return f"{prefix}{uuid.uuid4().hex[:8].upper()}"
        else:
            now = datetime.now()
            return f"{prefix}{now.strftime('%Y%m%d%H%M%S')}"


# ==================== 基础数据服务 ====================

class LocationService:
    model = "location"
    """库位管理服务"""

    @staticmethod
    async def get_by_id(location_id: int) -> Optional[StockLocation]:
        """根据ID获取库位"""
        return await StockLocation.filter(id=location_id).first()

    @staticmethod
    async def get_by_code(location_code: str) -> Optional[StockLocation]:
        """根据编码获取库位"""
        return await StockLocation.filter(location_code=location_code).first()

    @staticmethod
    async def create_location(data: StockLocationCreate) -> StockLocation:
        """创建库位"""
        # 检查编码是否存在
        if await LocationService.check_code_exists(data.location_code):
            raise ValueError(f"库位编码 {data.location_code} 已存在")

        # 如果有父库位，生成完整名称和路径
        complete_name = data.location_name
        path = data.location_code

        if data.parent_id:
            parent = await LocationService.get_by_id(data.parent_id)
            if parent:
                complete_name = f"{parent.complete_name}/{data.location_name}"
                path = f"{parent.path}/{data.location_code}"
                # 确保父库位编码一致
                if not data.parent_code:
                    data.parent_code = parent.location_code

        location_data = data.model_dump()
        location_data['complete_name'] = complete_name
        location_data['path'] = path

        return await StockLocation.create(**location_data)

    @staticmethod
    async def update_location(location_id: int, data: StockLocationUpdate) -> Optional[StockLocation]:
        """更新库位"""
        location = await LocationService.get_by_id(location_id)
        if not location:
            return None

        # 检查编码唯一性
        if data.location_code and data.location_code != location.location_code:
            if await LocationService.check_code_exists(data.location_code, exclude_id=location_id):
                raise ValueError(f"库位编码 {data.location_code} 已被使用")

        update_data = data.model_dump(exclude_none=True)

        # 如果父库位变更，重新生成完整名称和路径
        if 'parent_id' in update_data and update_data['parent_id'] != location.parent_id:
            parent = await LocationService.get_by_id(update_data['parent_id']) if update_data['parent_id'] else None
            loc_name = update_data.get('location_name', location.location_name)
            loc_code = update_data.get('location_code', location.location_code)

            if parent:
                update_data['complete_name'] = f"{parent.complete_name}/{loc_name}"
                update_data['path'] = f"{parent.path}/{loc_code}"
                update_data['parent_code'] = parent.location_code
            else:
                update_data['complete_name'] = loc_name
                update_data['path'] = loc_code
                update_data['parent_code'] = None

        await location.update_from_dict(update_data).save()
        return location

    @staticmethod
    async def delete_location(location_id: int) -> bool:
        """删除库位"""
        location = await LocationService.get_by_id(location_id)
        if not location:
            return False

        # 检查是否有子库位
        children_count = await StockLocation.filter(parent_id=location_id).count()
        if children_count > 0:
            raise ValueError("库位下存在子库位，无法删除")

        # 检查是否有库存
        quant_count = await StockQuant.filter(location_id=location_id).count()
        if quant_count > 0:
            raise ValueError("库位下存在库存，无法删除")

        await location.delete()
        return True

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockLocation], int]:
        """获取库位列表"""
        query = StockLocation.all()

        # 应用过滤条件
        for key, value in query_params.items():
            if value is not None:
                if key == 'location_code':
                    query = query.filter(location_code__icontains=value)
                elif key == 'location_name':
                    query = query.filter(location_name__icontains=value)
                elif key in ['parent_id', 'warehouse_id']:
                    query = query.filter(**{key: value})
                elif key == 'warehouse_code':
                    query = query.filter(warehouse_code__icontains=value)
                elif key in ['location_type', 'usage']:
                    query = query.filter(**{key: value})
                elif key == 'is_active':
                    query = query.filter(is_active=value)

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def get_children(location_id: int) -> List[StockLocation]:
        """获取子库位列表"""
        return await StockLocation.filter(parent_id=location_id).order_by('location_code')

    @staticmethod
    async def get_tree(location_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取库位树形结构"""
        if location_id:
            # 获取指定库位及其所有子库位
            root = await LocationService.get_by_id(location_id)
            if not root:
                return []

            children = await LocationService._build_tree(location_id)
            tree_data = await root.to_dict()
            tree_data['children'] = children
            return [tree_data]
        else:
            # 获取所有根库位
            roots = await StockLocation.filter(parent_id__isnull=True).order_by('location_code')
            tree = []
            for root in roots:
                tree_data = await root.to_dict()
                tree_data['children'] = await LocationService._build_tree(root.id)
                tree.append(tree_data)
            return tree

    @staticmethod
    async def _build_tree(parent_id: int) -> List[Dict[str, Any]]:
        """递归构建树形结构"""
        children = await StockLocation.filter(parent_id=parent_id).order_by('location_code')
        tree = []
        for child in children:
            child_data = await child.to_dict()
            child_data['children'] = await LocationService._build_tree(child.id)
            tree.append(child_data)
        return tree

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockLocation.filter(location_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class WarehouseService:
    model = "warehouse"
    """仓库管理服务"""

    @staticmethod
    async def get_by_id(warehouse_id: int) -> Optional[StockWarehouse]:
        """根据ID获取仓库"""
        return await StockWarehouse.filter(id=warehouse_id).first()

    @staticmethod
    async def get_by_code(warehouse_code: str) -> Optional[StockWarehouse]:
        """根据编码获取仓库"""
        return await StockWarehouse.filter(warehouse_code=warehouse_code).first()

    @staticmethod
    async def create_warehouse(data: StockWarehouseCreate) -> StockWarehouse:
        """创建仓库"""
        # 检查编码是否存在
        if await WarehouseService.check_code_exists(data.warehouse_code):
            raise ValueError(f"仓库编码 {data.warehouse_code} 已存在")

        warehouse = await StockWarehouse.create(**data.model_dump())

        # 如果提供了关键库位ID，验证库位是否存在
        location_fields = [
            'view_location_id', 'lot_stock_id', 'input_location_id',
            'output_location_id', 'qc_location_id', 'pack_location_id',
            'scrap_location_id'
        ]
        for field in location_fields:
            location_id = getattr(data, field, None)
            if location_id:
                location = await LocationService.get_by_id(location_id)
                if not location:
                    raise ValueError(f"库位ID {location_id} 不存在")

        return warehouse

    @staticmethod
    async def update_warehouse(warehouse_id: int, data: StockWarehouseUpdate) -> Optional[StockWarehouse]:
        """更新仓库"""
        warehouse = await WarehouseService.get_by_id(warehouse_id)
        if not warehouse:
            return None

        # 检查编码唯一性
        if data.warehouse_code and data.warehouse_code != warehouse.warehouse_code:
            if await WarehouseService.check_code_exists(data.warehouse_code, exclude_id=warehouse_id):
                raise ValueError(f"仓库编码 {data.warehouse_code} 已被使用")

        update_data = data.model_dump(exclude_none=True)
        await warehouse.update_from_dict(update_data).save()
        return warehouse

    @staticmethod
    async def delete_warehouse(warehouse_id: int) -> bool:
        """删除仓库"""
        warehouse = await WarehouseService.get_by_id(warehouse_id)
        if not warehouse:
            return False

        # 检查是否有关联库位
        location_count = await StockLocation.filter(warehouse_id=warehouse_id).count()
        if location_count > 0:
            raise ValueError("仓库下存在库位，无法删除")

        await warehouse.delete()
        return True

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockWarehouse], int]:
        """获取仓库列表"""
        query = StockWarehouse.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['warehouse_code', 'warehouse_name']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['warehouse_type', 'is_active']:
                    query = query.filter(**{key: value})

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockWarehouse.filter(warehouse_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class PickingTypeService:
    model = "picking_type"
    """调拨类型管理服务"""

    @staticmethod
    async def get_by_id(picking_type_id: int) -> Optional[StockPickingType]:
        """根据ID获取调拨类型"""
        return await StockPickingType.filter(id=picking_type_id).first()

    @staticmethod
    async def get_by_code(picking_type_code: str) -> Optional[StockPickingType]:
        """根据编码获取调拨类型"""
        return await StockPickingType.filter(picking_type_code=picking_type_code).first()

    @staticmethod
    async def create_picking_type(data: StockPickingTypeCreate) -> StockPickingType:
        """创建调拨类型"""
        # 检查编码是否存在
        if await PickingTypeService.check_code_exists(data.picking_type_code):
            raise ValueError(f"调拨类型编码 {data.picking_type_code} 已存在")

        # 验证仓库和库位
        if data.warehouse_id:
            warehouse = await WarehouseService.get_by_id(data.warehouse_id)
            if not warehouse:
                raise ValueError(f"仓库ID {data.warehouse_id} 不存在")

        if data.default_location_src_id:
            location = await LocationService.get_by_id(data.default_location_src_id)
            if not location:
                raise ValueError(f"源库位ID {data.default_location_src_id} 不存在")

        if data.default_location_dest_id:
            location = await LocationService.get_by_id(data.default_location_dest_id)
            if not location:
                raise ValueError(f"目标库位ID {data.default_location_dest_id} 不存在")

        return await StockPickingType.create(**data.model_dump())

    @staticmethod
    async def update_picking_type(picking_type_id: int, data: StockPickingTypeUpdate) -> Optional[StockPickingType]:
        """更新调拨类型"""
        picking_type = await PickingTypeService.get_by_id(picking_type_id)
        if not picking_type:
            return None

        # 检查编码唯一性
        if data.picking_type_code and data.picking_type_code != picking_type.picking_type_code:
            if await PickingTypeService.check_code_exists(data.picking_type_code, exclude_id=picking_type_id):
                raise ValueError(f"调拨类型编码 {data.picking_type_code} 已被使用")

        update_data = data.model_dump(exclude_none=True)
        await picking_type.update_from_dict(update_data).save()
        return picking_type

    @staticmethod
    async def delete_picking_type(picking_type_id: int) -> bool:
        """删除调拨类型"""
        picking_type = await PickingTypeService.get_by_id(picking_type_id)
        if not picking_type:
            return False

        # 检查是否有调拨单
        picking_count = await StockPicking.filter(picking_type_id=picking_type_id).count()
        if picking_count > 0:
            raise ValueError("调拨类型下存在调拨单，无法删除")

        await picking_type.delete()
        return True

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockPickingType], int]:
        """获取调拨类型列表"""
        query = StockPickingType.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['picking_type_code', 'picking_type_name']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['code', 'warehouse_id', 'warehouse_code', 'is_active']:
                    query = query.filter(**{key: value})

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def generate_next_sequence(picking_type_id: int) -> str:
        """生成下一个序列码"""
        picking_type = await PickingTypeService.get_by_id(picking_type_id)
        if not picking_type:
            raise ValueError("调拨类型不存在")

        # 更新序列号
        picking_type.last_sequence += 1
        await picking_type.save()

        # 生成序列码
        sequence_code = SequenceGenerator.generate_sequence_code(
            picking_type.sequence_code,
            picking_type.picking_type_code,
            picking_type.last_sequence - 1
        )

        return sequence_code

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockPickingType.filter(picking_type_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class LotService:
    model = "lot"
    """批次管理服务"""

    @staticmethod
    async def get_by_id(lot_id: int) -> Optional[StockLot]:
        """根据ID获取批次"""
        return await StockLot.filter(id=lot_id).first()

    @staticmethod
    async def get_by_code(lot_code: str) -> Optional[StockLot]:
        """根据编码获取批次"""
        return await StockLot.filter(lot_code=lot_code).first()

    @staticmethod
    async def create_lot(data: StockLotCreate) -> StockLot:
        """创建批次"""
        if await LotService.check_code_exists(data.lot_code):
            raise ValueError(f"批次编码 {data.lot_code} 已存在")

        return await StockLot.create(**data.model_dump())

    @staticmethod
    async def update_lot(lot_id: int, data: StockLotUpdate) -> Optional[StockLot]:
        """更新批次"""
        lot = await LotService.get_by_id(lot_id)
        if not lot:
            return None

        if data.lot_code and data.lot_code != lot.lot_code:
            if await LotService.check_code_exists(data.lot_code, exclude_id=lot_id):
                raise ValueError(f"批次编码 {data.lot_code} 已被使用")

        update_data = data.model_dump(exclude_none=True)
        await lot.update_from_dict(update_data).save()
        return lot

    @staticmethod
    async def delete_lot(lot_id: int) -> bool:
        """删除批次"""
        lot = await LotService.get_by_id(lot_id)
        if not lot:
            return False

        # 检查是否有库存使用该批次
        quant_count = await StockQuant.filter(lot_id=lot_id).count()
        if quant_count > 0:
            raise ValueError("批次下存在库存，无法删除")

        await lot.delete()
        return True

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockLot], int]:
        """获取批次列表"""
        query = StockLot.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['lot_code', 'lot_name', 'product_code']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['is_active']:
                    query = query.filter(**{key: value})
                elif key == 'expiry_date_start':
                    query = query.filter(expiry_date__gte=value)
                elif key == 'expiry_date_end':
                    query = query.filter(expiry_date__lte=value)

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockLot.filter(lot_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class PackageService:
    model = "package"
    """包裹管理服务"""

    @staticmethod
    async def get_by_id(package_id: int) -> Optional[StockPackage]:
        """根据ID获取包裹"""
        return await StockPackage.filter(id=package_id).first()

    @staticmethod
    async def get_by_code(package_code: str) -> Optional[StockPackage]:
        """根据编码获取包裹"""
        return await StockPackage.filter(package_code=package_code).first()

    @staticmethod
    async def create_package(data: StockPackageCreate) -> StockPackage:
        """创建包裹"""
        if await PackageService.check_code_exists(data.package_code):
            raise ValueError(f"包裹编码 {data.package_code} 已存在")

        # 验证库位
        if data.location_id:
            location = await LocationService.get_by_id(data.location_id)
            if not location:
                raise ValueError(f"库位ID {data.location_id} 不存在")

        # 验证父包裹
        if data.parent_id:
            parent = await PackageService.get_by_id(data.parent_id)
            if not parent:
                raise ValueError(f"父包裹ID {data.parent_id} 不存在")

        return await StockPackage.create(**data.model_dump())

    @staticmethod
    async def update_package(package_id: int, data: StockPackageUpdate) -> Optional[StockPackage]:
        """更新包裹"""
        package = await PackageService.get_by_id(package_id)
        if not package:
            return None

        if data.package_code and data.package_code != package.package_code:
            if await PackageService.check_code_exists(data.package_code, exclude_id=package_id):
                raise ValueError(f"包裹编码 {data.package_code} 已被使用")

        update_data = data.model_dump(exclude_none=True)
        await package.update_from_dict(update_data).save()
        return package

    @staticmethod
    async def delete_package(package_id: int) -> bool:
        """删除包裹"""
        package = await PackageService.get_by_id(package_id)
        if not package:
            return False

        # 检查是否有子包裹
        children_count = await StockPackage.filter(parent_id=package_id).count()
        if children_count > 0:
            raise ValueError("包裹下存在子包裹，无法删除")

        # 检查是否有库存使用该包裹
        quant_count = await StockQuant.filter(package_id=package_id).count()
        if quant_count > 0:
            raise ValueError("包裹下存在库存，无法删除")

        await package.delete()
        return True

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockPackage], int]:
        """获取包裹列表"""
        query = StockPackage.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['package_code', 'package_name', 'package_type']:
                    query = query.filter(**{f"{key}__icontains": value}) if key in ['package_code', 'package_name'] else query.filter(**{key: value})
                elif key in ['location_id', 'owner_id', 'parent_id', 'is_active']:
                    query = query.filter(**{key: value})

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockPackage.filter(package_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


# ==================== 调拨单服务 ====================

class PickingService:
    model = "picking"
    """调拨单全流程管理服务"""

    @staticmethod
    async def get_by_id(picking_id: int) -> Optional[StockPicking]:
        """根据ID获取调拨单"""
        return await StockPicking.filter(id=picking_id).first()

    @staticmethod
    async def get_by_code(picking_code: str) -> Optional[StockPicking]:
        """根据编码获取调拨单"""
        return await StockPicking.filter(picking_code=picking_code).first()

    @staticmethod
    async def create_picking(data: StockPickingCreate) -> StockPicking:
        """创建调拨单（自动生成编码）"""
        # 验证调拨类型
        picking_type = await PickingTypeService.get_by_id(data.picking_type_id)
        if not picking_type:
            raise ValueError(f"调拨类型ID {data.picking_type_id} 不存在")

        # 验证库位
        src_location = await LocationService.get_by_id(data.location_id)
        if not src_location:
            raise ValueError(f"源库位ID {data.location_id} 不存在")

        dest_location = await LocationService.get_by_id(data.location_dest_id)
        if not dest_location:
            raise ValueError(f"目标库位ID {data.location_dest_id} 不存在")

        # 生成调拨单编码
        if not data.picking_code:
            picking_code = await PickingTypeService.generate_next_sequence(data.picking_type_id)
        else:
            picking_code = data.picking_code
            if await PickingService.check_code_exists(picking_code):
                raise ValueError(f"调拨单编码 {picking_code} 已存在")

        # 准备调拨单数据
        picking_data = data.model_dump(exclude=['picking_code', 'moves'])
        picking_data['picking_code'] = picking_code
        picking_data['picking_type_code'] = picking_type.picking_type_code
        picking_data['picking_type_name'] = picking_type.picking_type_name
        picking_data['location_code'] = src_location.location_code
        picking_data['location_name'] = src_location.location_name
        picking_data['location_dest_code'] = dest_location.location_code
        picking_data['location_dest_name'] = dest_location.location_name

        # 创建调拨单
        picking = await StockPicking.create(**picking_data)

        # 创建移动明细
        if data.moves:
            for move_data in data.moves:
                move_data.picking_id = picking.id
                move_data.picking_code = picking_code
                await MoveService.create_move(move_data)

        return picking

    @staticmethod
    async def update_picking(picking_id: int, data: StockPickingUpdate) -> Optional[StockPicking]:
        """更新调拨单"""
        picking = await PickingService.get_by_id(picking_id)
        if not picking:
            return None

        # 只允许在draft状态更新
        if picking.state != 'draft':
            raise ValueError(f"调拨单状态为 {picking.state}，无法更新")

        update_data = data.model_dump(exclude_none=True)
        await picking.update_from_dict(update_data).save()
        return picking

    @staticmethod
    async def delete_picking(picking_id: int) -> bool:
        """删除调拨单（仅draft/cancel状态）"""
        picking = await PickingService.get_by_id(picking_id)
        if not picking:
            return False

        if picking.state not in ('draft', 'cancel'):
            raise ValueError(f"调拨单状态为 {picking.state}，无法删除")

        # 删除移动明细和明细行
        moves = await StockMove.filter(picking_id=picking_id)
        for move in moves:
            await StockMoveLine.filter(move_id=move.id).delete()
            await move.delete()

        await picking.delete()
        return True

    @staticmethod
    async def confirm_picking(picking_id: int) -> StockPicking:
        """确认调拨单（检查库存可用性，创建预留）"""
        picking = await PickingService.get_by_id(picking_id)
        if not picking:
            raise ValueError("调拨单不存在")

        if picking.state != 'draft':
            raise ValueError(f"调拨单状态为 {picking.state}，无法确认")

        # 获取所有移动明细
        moves = await StockMove.filter(picking_id=picking_id)

        # 检查库存可用性并预留
        for move in moves:
            await MoveService.reserve_move(move.id)

        # 更新调拨单状态
        picking.state = 'confirmed'
        await picking.save()

        return picking

    @staticmethod
    async def assign_picking(picking_id: int) -> StockPicking:
        """分配库存（更新预留状态）"""
        picking = await PickingService.get_by_id(picking_id)
        if not picking:
            raise ValueError("调拨单不存在")

        if picking.state not in ('confirmed', 'partially_available'):
            raise ValueError(f"调拨单状态为 {picking.state}，无法分配")

        # 获取所有移动明细并分配
        moves = await StockMove.filter(picking_id=picking_id)
        all_assigned = True

        for move in moves:
            try:
                await MoveService.assign_move(move.id)
            except ValueError:
                all_assigned = False

        # 更新调拨单状态
        if all_assigned:
            picking.state = 'assigned'
        else:
            picking.state = 'partially_available'
        await picking.save()

        return picking

    @staticmethod
    async def do_picking(picking_id: int) -> StockPicking:
        """完成调拨单（更新库存数量，生成交易记录）"""
        picking = await PickingService.get_by_id(picking_id)
        if not picking:
            raise ValueError("调拨单不存在")

        if picking.state not in ('confirmed', 'assigned', 'partially_available'):
            raise ValueError(f"调拨单状态为 {picking.state}，无法完成")

        # 获取所有移动明细并完成
        moves = await StockMove.filter(picking_id=picking_id)
        all_done = True
        any_partial = False

        for move in moves:
            try:
                await MoveService.do_move(move.id)
            except ValueError as e:
                if "部分完成" in str(e):
                    all_done = False
                    any_partial = True
                else:
                    raise

        # 如果需要回单（部分完成）
        if any_partial:
            await PickingService.create_backorder(picking_id)

        # 更新调拨单状态
        if all_done:
            picking.state = 'done'
            picking.date_done = datetime.now()
        else:
            picking.state = 'partially_available'
        await picking.save()

        return picking

    @staticmethod
    async def cancel_picking(picking_id: int) -> StockPicking:
        """取消调拨单（释放预留）"""
        picking = await PickingService.get_by_id(picking_id)
        if not picking:
            raise ValueError("调拨单不存在")

        if picking.state == 'done':
            raise ValueError("已完成的调拨单无法取消")

        # 释放所有预留
        moves = await StockMove.filter(picking_id=picking_id)
        for move in moves:
            await MoveService.unreserve_move(move.id)

        # 更新调拨单状态
        picking.state = 'cancel'
        await picking.save()

        return picking

    @staticmethod
    async def create_backorder(picking_id: int) -> StockPicking:
        """创建回单（部分完成时）"""
        picking = await PickingService.get_by_id(picking_id)
        if not picking:
            raise ValueError("调拨单不存在")

        # 生成回单编码
        backorder_code = f"{picking.picking_code}-BO"

        # 创建回单
        backorder_data = {
            'picking_code': backorder_code,
            'picking_type_id': picking.picking_type_id,
            'picking_type_code': picking.picking_type_code,
            'picking_type_name': picking.picking_type_name,
            'origin': picking.origin,
            'origin_type': picking.origin_type,
            'partner_code': picking.partner_code,
            'partner_name': picking.partner_name,
            'location_id': picking.location_id,
            'location_code': picking.location_code,
            'location_name': picking.location_name,
            'location_dest_id': picking.location_dest_id,
            'location_dest_code': picking.location_dest_code,
            'location_dest_name': picking.location_dest_name,
            'move_type': picking.move_type,
            'state': 'draft',
            'scheduled_date': picking.scheduled_date,
            'priority': picking.priority,
            'company_code': picking.company_code,
            'backorder_id': picking.id,
        }

        backorder = await StockPicking.create(**backorder_data)

        # 关联回单
        picking.backorder_id = backorder.id
        picking.backorder_code = backorder_code
        await picking.save()

        return backorder

    @staticmethod
    async def get_moves_by_picking_id(picking_id: int) -> List[StockMove]:
        """获取调拨单的所有移动明细"""
        return await StockMove.filter(picking_id=picking_id).order_by('id')

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockPicking], int]:
        """获取调拨单列表"""
        query = StockPicking.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['picking_code', 'origin', 'partner_code']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['picking_type_id', 'location_id', 'location_dest_id', 'state', 'priority']:
                    query = query.filter(**{key: value})
                elif key in ['picking_type_code']:
                    query = query.filter(**{key: value})
                elif key == 'scheduled_date_start':
                    query = query.filter(scheduled_date__gte=value)
                elif key == 'scheduled_date_end':
                    query = query.filter(scheduled_date__lte=value)

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockPicking.filter(picking_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class MoveService:
    model = "move"
    """移动明细管理服务"""

    @staticmethod
    async def get_by_id(move_id: int) -> Optional[StockMove]:
        """根据ID获取移动明细"""
        return await StockMove.filter(id=move_id).first()

    @staticmethod
    async def get_by_code(move_code: str) -> Optional[StockMove]:
        """根据编码获取移动明细"""
        return await StockMove.filter(move_code=move_code).first()

    @staticmethod
    async def create_move(data: StockMoveCreate) -> StockMove:
        """创建移动明细"""
        # 验证调拨单
        picking = await PickingService.get_by_id(data.picking_id)
        if not picking:
            raise ValueError(f"调拨单ID {data.picking_id} 不存在")

        # 验证库位
        src_location = await LocationService.get_by_id(data.location_id)
        if not src_location:
            raise ValueError(f"源库位ID {data.location_id} 不存在")

        dest_location = await LocationService.get_by_id(data.location_dest_id)
        if not dest_location:
            raise ValueError(f"目标库位ID {data.location_dest_id} 不存在")

        # 生成移动编码
        if not data.move_code:
            move_code = SequenceGenerator.generate_code(prefix="MV")
        else:
            move_code = data.move_code
            if await MoveService.check_code_exists(move_code):
                raise ValueError(f"移动编码 {move_code} 已存在")

        # 准备移动明细数据
        move_data = data.model_dump(exclude=['move_code', 'move_lines'])
        move_data['move_code'] = move_code
        move_data['picking_code'] = picking.picking_code
        move_data['location_code'] = src_location.location_code
        move_data['location_name'] = src_location.location_name
        move_data['location_dest_code'] = dest_location.location_code
        move_data['location_dest_name'] = dest_location.location_name

        # 创建移动明细
        move = await StockMove.create(**move_data)

        # 创建移动明细行
        if data.move_lines:
            for line_data in data.move_lines:
                line_data.move_id = move.id
                line_data.move_code = move_code
                line_data.picking_id = picking.id
                line_data.picking_code = picking.picking_code
                await MoveLineService.create_move_line(line_data)

        return move

    @staticmethod
    async def reserve_move(move_id: int) -> None:
        """预留库存"""
        move = await MoveService.get_by_id(move_id)
        if not move:
            raise ValueError("移动明细不存在")

        if move.state != 'draft':
            raise ValueError(f"移动明细状态为 {move.state}，无法预留")

        # 获取可用库存
        available_quants = await QuantService.get_available_quants(
            move.product_code,
            move.location_id,
            move.product_uom_qty
        )

        # 计算总可用数量
        total_available = sum(q.available_quantity for q in available_quants)
        if total_available < move.product_uom_qty:
            raise ValueError(f"产品 {move.product_code} 库存不足，需 {move.product_uom_qty}，可用 {total_available}")

        # 创建预留记录
        reserved_qty = Decimal('0')
        for quant in available_quants:
            # 计算本次预留数量
            qty_to_reserve = min(quant.available_quantity, move.product_uom_qty - reserved_qty)

            # 创建预留
            reservation_data = {
                'quant_id': quant.id,
                'quant_code': quant.quant_code,
                'move_id': move.id,
                'move_code': move.move_code,
                'product_code': move.product_code,
                'location_id': quant.location_id,
                'location_code': quant.location_code,
                'lot_id': quant.lot_id,
                'lot_name': quant.lot_name,
                'serial_no': quant.serial_no,
                'quantity': qty_to_reserve,
                'reserved_at': datetime.now(),
                'state': 'reserved',
            }
            await ReservationService.create_reservation(StockQuantReservationCreate(**reservation_data))

            # 更新库存预留数量
            await QuantService.reserve_quant(quant.id, qty_to_reserve)

            reserved_qty += qty_to_reserve
            if reserved_qty >= move.product_uom_qty:
                break

        # 更新移动明细状态和预留数量
        move.state = 'confirmed'
        move.reserved_quantity = reserved_qty
        await move.save()

    @staticmethod
    async def unreserve_move(move_id: int) -> None:
        """释放预留"""
        move = await MoveService.get_by_id(move_id)
        if not move:
            raise ValueError("移动明细不存在")

        # 获取所有预留记录
        reservations = await StockQuantReservation.filter(move_id=move_id, state='reserved')

        # 释放预留
        for reservation in reservations:
            await ReservationService.release_reservation(reservation.id)

        # 更新移动明细状态和预留数量
        move.state = 'draft'
        move.reserved_quantity = Decimal('0')
        await move.save()

    @staticmethod
    async def do_move(move_id: int) -> None:
        """完成移动明细"""
        move = await MoveService.get_by_id(move_id)
        if not move:
            raise ValueError("移动明细不存在")

        if move.state not in ('confirmed', 'assigned', 'partially_available'):
            raise ValueError(f"移动明细状态为 {move.state}，无法完成")

        # 获取明细行
        move_lines = await StockMoveLine.filter(move_id=move_id)

        # 如果没有明细行，根据预留自动创建
        if not move_lines:
            reservations = await StockQuantReservation.filter(move_id=move_id, state='reserved')
            for reservation in reservations:
                # 查询源库位名称
                src_location = await LocationService.get_by_id(reservation.location_id)
                location_name = src_location.location_name if src_location else ''

                # 创建明细行
                line_data = {
                    'picking_id': move.picking_id,
                    'picking_code': move.picking_code,
                    'move_id': move.id,
                    'move_code': move.move_code,
                    'product_code': move.product_code,
                    'product_name': move.product_name,
                    'product_uom': move.product_uom,
                    'product_uom_qty': reservation.quantity,
                    'qty_done': reservation.quantity,
                    'location_id': reservation.location_id,
                    'location_code': reservation.location_code,
                    'location_name': location_name,
                    'location_dest_id': move.location_dest_id,
                    'location_dest_code': move.location_dest_code,
                    'location_dest_name': move.location_dest_name,
                    'lot_id': reservation.lot_id,
                    'lot_name': reservation.lot_name,
                    'serial_no': reservation.serial_no,
                    'state': 'done',
                    'is_done': True,
                }
                new_line = await MoveLineService.create_move_line(StockMoveLineCreate(**line_data))

                # 更新预留记录的 move_line_id
                reservation.move_line_id = new_line.id
                reservation.move_line_code = new_line.move_line_code
                await reservation.save()

        # 重新获取明细行（包括刚创建的）
        move_lines = await StockMoveLine.filter(move_id=move_id)

        # 计算已完成数量
        total_done = sum(line.qty_done for line in move_lines)

        # 如果部分完成
        if total_done < move.product_uom_qty:
            move.state = 'partially_available'
            move.quantity_done = total_done
            await move.save()
            raise ValueError(f"部分完成：已完成 {total_done}，需求 {move.product_uom_qty}")

        # 更新库存
        for line in move_lines:
            # 消费预留（通过move_id查找预留）
            reservations = await StockQuantReservation.filter(move_id=move.id, move_line_id=line.id, state='reserved')
            for reservation in reservations:
                await ReservationService.consume_reservation(reservation.id)

            # 从源库位减少库存
            await QuantService.update_quantity(
                line.product_code,
                line.location_id,
                -line.qty_done,
                lot_id=line.lot_id,
                serial_no=line.serial_no,
                product_name=line.product_name
            )

            # 在目标库位增加库存
            await QuantService.update_quantity(
                line.product_code,
                line.location_dest_id,
                line.qty_done,
                lot_id=line.lot_id,
                serial_no=line.serial_no,
                product_name=line.product_name
            )

        # 更新移动明细状态
        move.state = 'done'
        move.quantity_done = total_done
        await move.save()

    @staticmethod
    async def assign_move(move_id: int) -> None:
        """分配移动明细"""
        move = await MoveService.get_by_id(move_id)
        if not move:
            raise ValueError("移动明细不存在")

        if move.state != 'confirmed':
            raise ValueError(f"移动明细状态为 {move.state}，无法分配")

        # 检查预留是否足够
        if move.reserved_quantity >= move.product_uom_qty:
            move.state = 'assigned'
            await move.save()
        else:
            # 尝试预留更多库存
            needed_qty = move.product_uom_qty - move.reserved_quantity
            try:
                available_quants = await QuantService.get_available_quants(
                    move.product_code,
                    move.location_id,
                    needed_qty
                )
                for quant in available_quants:
                    qty_to_reserve = min(quant.available_quantity, needed_qty)
                    reservation_data = {
                        'quant_id': quant.id,
                        'quant_code': quant.quant_code,
                        'move_id': move.id,
                        'move_code': move.move_code,
                        'product_code': move.product_code,
                        'location_id': quant.location_id,
                        'location_code': quant.location_code,
                        'lot_id': quant.lot_id,
                        'lot_name': quant.lot_name,
                        'serial_no': quant.serial_no,
                        'quantity': qty_to_reserve,
                        'reserved_at': datetime.now(),
                        'state': 'reserved',
                    }
                    await ReservationService.create_reservation(StockQuantReservationCreate(**reservation_data))
                    await QuantService.reserve_quant(quant.id, qty_to_reserve)

                    move.reserved_quantity += qty_to_reserve
                    needed_qty -= qty_to_reserve
                    if needed_qty <= 0:
                        break

                move.state = 'assigned'
            except Exception:
                move.state = 'partially_available'

            await move.save()

    @staticmethod
    async def update_quantity_done(move_id: int, quantity_done: Decimal) -> StockMove:
        """更新已完成数量"""
        move = await MoveService.get_by_id(move_id)
        if not move:
            raise ValueError("移动明细不存在")

        if quantity_done > move.product_uom_qty:
            raise ValueError(f"已完成数量 {quantity_done} 超过需求数量 {move.product_uom_qty}")

        move.quantity_done = quantity_done
        await move.save()
        return move

    @staticmethod
    async def get_move_lines_by_move_id(move_id: int) -> List[StockMoveLine]:
        """获取移动明细的所有明细行"""
        return await StockMoveLine.filter(move_id=move_id).order_by('id')

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockMove], int]:
        """获取移动明细列表"""
        query = StockMove.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['move_code', 'picking_code', 'product_code']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['picking_id', 'location_id', 'location_dest_id', 'state']:
                    query = query.filter(**{key: value})
                elif key == 'date_expected_start':
                    query = query.filter(date_expected__gte=value)
                elif key == 'date_expected_end':
                    query = query.filter(date_expected__lte=value)

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockMove.filter(move_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class MoveLineService:
    model = "move_line"
    """移动明细行管理服务"""

    @staticmethod
    async def get_by_id(move_line_id: int) -> Optional[StockMoveLine]:
        """根据ID获取移动明细行"""
        return await StockMoveLine.filter(id=move_line_id).first()

    @staticmethod
    async def get_by_code(move_line_code: str) -> Optional[StockMoveLine]:
        """根据编码获取移动明细行"""
        return await StockMoveLine.filter(move_line_code=move_line_code).first()

    @staticmethod
    async def create_move_line(data: StockMoveLineCreate) -> StockMoveLine:
        """创建移动明细行（支持批次/序列号）"""
        # 验证移动明细
        move = await MoveService.get_by_id(data.move_id)
        if not move:
            raise ValueError(f"移动明细ID {data.move_id} 不存在")

        # 验证库位
        src_location = await LocationService.get_by_id(data.location_id)
        if not src_location:
            raise ValueError(f"源库位ID {data.location_id} 不存在")

        dest_location = await LocationService.get_by_id(data.location_dest_id)
        if not dest_location:
            raise ValueError(f"目标库位ID {data.location_dest_id} 不存在")

        # 验证批次
        if data.lot_id:
            lot = await LotService.get_by_id(data.lot_id)
            if not lot:
                raise ValueError(f"批次ID {data.lot_id} 不存在")

        # 验证包裹
        if data.package_id:
            package = await PackageService.get_by_id(data.package_id)
            if not package:
                raise ValueError(f"包裹ID {data.package_id} 不存在")

        # 生成明细行编码
        if not data.move_line_code:
            move_line_code = SequenceGenerator.generate_code(prefix="ML")
        else:
            move_line_code = data.move_line_code
            if await MoveLineService.check_code_exists(move_line_code):
                raise ValueError(f"明细行编码 {move_line_code} 已存在")

        # 准备明细行数据
        line_data = data.model_dump(exclude=['move_line_code'])
        line_data['move_line_code'] = move_line_code
        line_data['picking_code'] = move.picking_code
        line_data['move_code'] = move.move_code
        line_data['location_code'] = src_location.location_code
        line_data['location_name'] = src_location.location_name
        line_data['location_dest_code'] = dest_location.location_code
        line_data['location_dest_name'] = dest_location.location_name

        return await StockMoveLine.create(**line_data)

    @staticmethod
    async def update_qty_done(move_line_id: int, qty_done: Decimal) -> StockMoveLine:
        """更新已完成数量"""
        line = await MoveLineService.get_by_id(move_line_id)
        if not line:
            raise ValueError("明细行不存在")

        if qty_done > line.product_uom_qty:
            raise ValueError(f"已完成数量 {qty_done} 超过需求数量 {line.product_uom_qty}")

        line.qty_done = qty_done
        if qty_done > 0:
            line.state = 'assigned'
        if qty_done == line.product_uom_qty:
            line.state = 'done'
            line.is_done = True

        await line.save()
        return line

    @staticmethod
    async def assign_move_line(move_line_id: int, lot_id: Optional[int] = None, serial_no: Optional[str] = None) -> StockMoveLine:
        """分配批次/序列号"""
        line = await MoveLineService.get_by_id(move_line_id)
        if not line:
            raise ValueError("明细行不存在")

        if lot_id:
            lot = await LotService.get_by_id(lot_id)
            if not lot:
                raise ValueError(f"批次ID {lot_id} 不存在")
            if lot.product_code != line.product_code:
                raise ValueError(f"批次产品 {lot.product_code} 与明细行产品 {line.product_code} 不匹配")
            line.lot_id = lot_id
            line.lot_name = lot.lot_name

        if serial_no:
            line.serial_no = serial_no

        line.state = 'assigned'
        await line.save()
        return line

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockMoveLine], int]:
        """获取移动明细行列表"""
        query = StockMoveLine.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['move_line_code', 'lot_name', 'serial_no']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['picking_id', 'move_id', 'lot_id', 'location_id', 'location_dest_id', 'state', 'is_done', 'product_code']:
                    query = query.filter(**{key: value})

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockMoveLine.filter(move_line_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


# ==================== 库存服务 ====================

class QuantService:
    model = "quant"
    """库存数量管理服务"""

    @staticmethod
    async def get_by_id(quant_id: int) -> Optional[StockQuant]:
        """根据ID获取库存"""
        return await StockQuant.filter(id=quant_id).first()

    @staticmethod
    async def get_by_code(quant_code: str) -> Optional[StockQuant]:
        """根据编码获取库存"""
        return await StockQuant.filter(quant_code=quant_code).first()

    @staticmethod
    async def get_quant(product_code: str, location_id: int, lot_id: Optional[int] = None, serial_no: Optional[str] = None) -> Optional[StockQuant]:
        """按产品+库位+批次+序列号查询库存"""
        query = StockQuant.filter(
            product_code=product_code,
            location_id=location_id
        )
        if lot_id:
            query = query.filter(lot_id=lot_id)
        if serial_no:
            query = query.filter(serial_no=serial_no)

        return await query.first()

    @staticmethod
    async def get_available_quants(product_code: str, location_id: int, required_qty: Decimal) -> List[StockQuant]:
        """获取可用库存（按FIFO排序）"""
        # 查询可用库存，按入库日期升序排列（FIFO）
        quants = await StockQuant.filter(
            product_code=product_code,
            location_id=location_id,
            available_quantity__gt=0
        ).order_by('in_date')

        return quants

    @staticmethod
    async def create_quant(data: StockQuantCreate) -> StockQuant:
        """创建库存数量"""
        # 检查是否已存在相同维度的库存
        existing_quant = await QuantService.get_quant(
            data.product_code,
            data.location_id,
            data.lot_id,
            data.serial_no
        )

        if existing_quant:
            # 如果存在，更新数量
            existing_quant.quantity += data.quantity
            existing_quant.available_quantity = existing_quant.quantity - existing_quant.reserved_quantity
            existing_quant.inventory_value = existing_quant.quantity * (existing_quant.cost or Decimal('0'))
            await existing_quant.save()
            return existing_quant

        # 生成库存编码
        if not data.quant_code:
            quant_code = SequenceGenerator.generate_code(prefix="QT")
        else:
            quant_code = data.quant_code
            if await QuantService.check_code_exists(quant_code):
                raise ValueError(f"库存编码 {quant_code} 已存在")

        # 验证库位
        location = await LocationService.get_by_id(data.location_id)
        if not location:
            raise ValueError(f"库位ID {data.location_id} 不存在")

        # 验证批次
        if data.lot_id:
            lot = await LotService.get_by_id(data.lot_id)
            if not lot:
                raise ValueError(f"批次ID {data.lot_id} 不存在")

        # 准备库存数据
        quant_data = data.model_dump(exclude=['quant_code'])
        quant_data['quant_code'] = quant_code
        quant_data['location_code'] = location.location_code
        quant_data['location_name'] = location.location_name
        quant_data['available_quantity'] = data.quantity - data.reserved_quantity
        
        # 如果没有提供product_id，尝试从产品模块查询
        if not quant_data.get('product_id') and PRODUCT_AVAILABLE and Product is not None:
            product = await Product.filter(name=data.product_code).first()
            if product:
                quant_data['product_id'] = product.id
                if not quant_data.get('product_name'):
                    quant_data['product_name'] = product.name
                # 填充单位信息
                if not quant_data.get('uom_code'):
                    quant_data['uom_code'] = getattr(product, 'uom_code', 'unit')
                if not quant_data.get('uom_name'):
                    quant_data['uom_name'] = getattr(product, 'uom_name', '件')
                if not quant_data.get('secondary_uom_name'):
                    quant_data['secondary_uom_name'] = getattr(product, 'secondary_uom_name', None)
                if not quant_data.get('conversion_factor'):
                    quant_data['conversion_factor'] = getattr(product, 'conversion_factor', 1)
        
        if data.lot_id:
            lot = await LotService.get_by_id(data.lot_id)
            quant_data['lot_name'] = lot.lot_name if lot else None

        return await StockQuant.create(**quant_data)

    @staticmethod
    async def update_quantity(product_code: str, location_id: int, quantity_delta: Decimal, lot_id: Optional[int] = None, serial_no: Optional[str] = None, cost: Optional[Decimal] = None, product_name: Optional[str] = None) -> StockQuant:
        """更新库存数量"""
        # 查找库存记录
        quant = await QuantService.get_quant(product_code, location_id, lot_id, serial_no)

        if not quant:
            # 如果库存不存在且是增加数量，创建新库存
            if quantity_delta > 0:
                quant_data = {
                    'product_code': product_code,
                    'product_name': product_name or '',
                    'location_id': location_id,
                    'lot_id': lot_id,
                    'serial_no': serial_no,
                    'quantity': quantity_delta,
                    'reserved_quantity': Decimal('0'),
                    'available_quantity': quantity_delta,
                    'cost': cost or Decimal('0'),
                    'in_date': datetime.now(),
                }
                # 需要补充location_code等字段
                location = await LocationService.get_by_id(location_id)
                if location:
                    quant_data['location_code'] = location.location_code
                    quant_data['location_name'] = location.location_name

                if lot_id:
                    lot = await LotService.get_by_id(lot_id)
                    if lot:
                        quant_data['lot_name'] = lot.lot_name

                # 尝试从产品模块查询产品信息
                if PRODUCT_AVAILABLE and Product is not None:
                    product = await Product.filter(name=product_code).first()
                    if product:
                        quant_data['product_id'] = product.id
                        if not quant_data.get('product_name'):
                            quant_data['product_name'] = product.name

                return await QuantService.create_quant(StockQuantCreate(**quant_data))
            else:
                raise ValueError(f"产品 {product_code} 在库位 {location_id} 的库存不存在")

        # 更新数量
        new_quantity = quant.quantity + quantity_delta
        if new_quantity < Decimal('0'):
            raise ValueError(f"库存数量不能为负数（当前：{quant.quantity}，调整：{quantity_delta}）")

        quant.quantity = new_quantity
        quant.available_quantity = quant.quantity - quant.reserved_quantity
        if cost:
            quant.cost = cost
        quant.inventory_value = quant.quantity * (quant.cost or Decimal('0'))
        await quant.save()

        return quant

    @staticmethod
    async def reserve_quant(quant_id: int, quantity: Decimal) -> StockQuant:
        """预留库存"""
        quant = await QuantService.get_by_id(quant_id)
        if not quant:
            raise ValueError("库存不存在")

        if quantity > quant.available_quantity:
            raise ValueError(f"预留数量 {quantity} 超过可用数量 {quant.available_quantity}")

        quant.reserved_quantity += quantity
        quant.available_quantity = quant.quantity - quant.reserved_quantity
        await quant.save()

        return quant

    @staticmethod
    async def unreserve_quant(quant_id: int, quantity: Decimal) -> StockQuant:
        """释放预留"""
        quant = await QuantService.get_by_id(quant_id)
        if not quant:
            raise ValueError("库存不存在")

        if quantity > quant.reserved_quantity:
            raise ValueError(f"释放数量 {quantity} 超过预留数量 {quant.reserved_quantity}")

        quant.reserved_quantity -= quantity
        quant.available_quantity = quant.quantity - quant.reserved_quantity
        await quant.save()

        return quant

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockQuant], int]:
        """获取库存列表"""
        query = StockQuant.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['quant_code', 'product_code', 'lot_name', 'serial_no']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['location_id', 'lot_id', 'owner_id']:
                    query = query.filter(**{key: value})
                elif key == 'location_code':
                    query = query.filter(location_code__icontains=value)
                elif key == 'in_date_start':
                    query = query.filter(in_date__gte=value)
                elif key == 'in_date_end':
                    query = query.filter(in_date__lte=value)
                elif key == 'expiry_date_start':
                    query = query.filter(expiry_date__gte=value)
                elif key == 'expiry_date_end':
                    query = query.filter(expiry_date__lte=value)

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def get_by_product(product_code: str) -> List[StockQuant]:
        """按产品查询库存"""
        return await StockQuant.filter(product_code=product_code).order_by('location_code')

    @staticmethod
    async def get_by_location(location_id: int) -> List[StockQuant]:
        """按库位查询库存"""
        return await StockQuant.filter(location_id=location_id).order_by('product_code')

    @staticmethod
    async def get_summary(product_code: Optional[str] = None) -> Dict[str, Any]:
        """获取库存汇总统计"""
        query = StockQuant.all()
        if product_code:
            query = query.filter(product_code=product_code)

        quants = await query
        
        total_quantity = sum(q.quantity for q in quants)
        total_reserved = sum(q.reserved_quantity for q in quants)
        total_available = sum(q.available_quantity for q in quants)
        total_value = sum(q.inventory_value for q in quants)
        total_sku = len(set(q.product_code for q in quants))

        location_dict = {}
        for q in quants:
            loc_key = q.location_id or q.location_code or 'unknown'
            if loc_key not in location_dict:
                location_dict[loc_key] = {
                    'location_name': q.location_name or '未知',
                    'sku_count': 0,
                    'total_quantity': 0,
                    'total_reserved': 0
                }
            location_dict[loc_key]['sku_count'] += 1
            location_dict[loc_key]['total_quantity'] += q.quantity
            location_dict[loc_key]['total_reserved'] += q.reserved_quantity

        return {
            'product_code': product_code,
            'total_sku': total_sku,
            'total_quantity': total_quantity,
            'total_reserved': total_reserved,
            'total_available': total_available,
            'total_value': total_value,
            'location_count': len(location_dict),
            'lot_count': len(set(q.lot_id for q in quants if q.lot_id)),
            'by_location': list(location_dict.values())
        }

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockQuant.filter(quant_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class ReservationService:
    model = "reservation"
    """库存预留管理服务"""

    @staticmethod
    async def get_by_id(reservation_id: int) -> Optional[StockQuantReservation]:
        """根据ID获取预留"""
        return await StockQuantReservation.filter(id=reservation_id).first()

    @staticmethod
    async def get_by_code(reservation_code: str) -> Optional[StockQuantReservation]:
        """根据编码获取预留"""
        return await StockQuantReservation.filter(reservation_code=reservation_code).first()

    @staticmethod
    async def create_reservation(data: StockQuantReservationCreate) -> StockQuantReservation:
        """创建预留记录"""
        # 生成预留编码
        if not data.reservation_code:
            reservation_code = SequenceGenerator.generate_code(prefix="RS")
        else:
            reservation_code = data.reservation_code
            if await ReservationService.check_code_exists(reservation_code):
                raise ValueError(f"预留编码 {reservation_code} 已存在")

        # 验证库存
        quant = await QuantService.get_by_id(data.quant_id)
        if not quant:
            raise ValueError(f"库存ID {data.quant_id} 不存在")

        # 验证移动明细
        move = await MoveService.get_by_id(data.move_id)
        if not move:
            raise ValueError(f"移动明细ID {data.move_id} 不存在")

        # 准备预留数据
        reservation_data = data.model_dump(exclude=['reservation_code'])
        reservation_data['reservation_code'] = reservation_code
        reservation_data['quant_code'] = quant.quant_code
        reservation_data['move_code'] = move.move_code
        reservation_data['location_code'] = quant.location_code

        return await StockQuantReservation.create(**reservation_data)

    @staticmethod
    async def release_reservation(reservation_id: int) -> StockQuantReservation:
        """释放预留"""
        reservation = await ReservationService.get_by_id(reservation_id)
        if not reservation:
            raise ValueError("预留不存在")

        if reservation.state != 'reserved':
            raise ValueError(f"预留状态为 {reservation.state}，无法释放")

        # 释放库存预留
        await QuantService.unreserve_quant(reservation.quant_id, reservation.quantity)

        # 更新预留状态
        reservation.state = 'released'
        reservation.released_at = datetime.now()
        await reservation.save()

        return reservation

    @staticmethod
    async def consume_reservation(reservation_id: int) -> StockQuantReservation:
        """消费预留"""
        reservation = await ReservationService.get_by_id(reservation_id)
        if not reservation:
            raise ValueError("预留不存在")

        if reservation.state not in ('reserved', 'released'):
            raise ValueError(f"预留状态为 {reservation.state}，无法消费")

        # 释放库存预留数量
        await QuantService.unreserve_quant(reservation.quant_id, reservation.quantity)

        # 更新预留状态
        reservation.state = 'consumed'
        await reservation.save()

        return reservation

    @staticmethod
    async def consume_reservation_by_move_line(move_line_id: int) -> List[StockQuantReservation]:
        """根据移动明细行消费预留"""
        reservations = await StockQuantReservation.filter(move_line_id=move_line_id, state='reserved')

        for reservation in reservations:
            await ReservationService.consume_reservation(reservation.id)

        return reservations

    @staticmethod
    async def get_list(**query_params) -> Tuple[List[StockQuantReservation], int]:
        """获取预留列表"""
        query = StockQuantReservation.all()

        for key, value in query_params.items():
            if value is not None:
                if key in ['reservation_code', 'lot_name', 'serial_no']:
                    query = query.filter(**{f"{key}__icontains": value})
                elif key in ['quant_id', 'move_id', 'move_line_id', 'location_id', 'lot_id', 'state']:
                    query = query.filter(**{key: value})
                elif key == 'reserved_at_start':
                    query = query.filter(reserved_at__gte=value)
                elif key == 'reserved_at_end':
                    query = query.filter(reserved_at__lte=value)

        total = await query.count()
        page = query_params.get('page', 1)
        page_size = query_params.get('page_size', 10)
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')

        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查编码是否存在"""
        query = StockQuantReservation.filter(reservation_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()
