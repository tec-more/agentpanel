from typing import Optional, List, Tuple, Dict, Any
from decimal import Decimal
from tortoise.expressions import Q
try:
    from base.plugins.mes.models.base_data import Material, Bom, BomVersion, WorkCenter, Process, Route, RouteProcess
    from base.plugins.mes.schemas.mes_schema import (
        MaterialCreate, MaterialUpdate,
        BomCreate, BomUpdate,
        WorkCenterCreate, WorkCenterUpdate,
        ProcessCreate, ProcessUpdate,
        RouteCreate, RouteUpdate,
    )
    try:
        from base.plugins.product.models.product import Product
        PRODUCT_AVAILABLE = True
    except ImportError:
        Product = None
        PRODUCT_AVAILABLE = False
except ImportError:
    from typing import Any
    from datetime import datetime
    from decimal import Decimal

    class BaseModelMock:
        id = 1
        created_at = datetime.now()
        updated_at = datetime.now()

        async def save(self):
            pass

        async def update_from_dict(self, data):
            for key, value in data.items():
                setattr(self, key, value)
            return self

    class Material(BaseModelMock):
        def __init__(self, **kwargs):
            super().__init__()
            for key, value in kwargs.items():
                setattr(self, key, value)

        @classmethod
        async def create(cls, **kwargs):
            return cls(**kwargs)

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
                def distinct(self): return self
                def values_list(self, field, flat=False): return []
            return MockQuerySet()

        async def to_dict(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    class Bom(Material): pass
    class WorkCenter(Material): pass
    class Process(Material): pass
    class Route(Material): pass

    class MaterialCreate:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class MaterialUpdate(MaterialCreate):
        def model_dump(self, exclude_none=False):
            return {k: v for k, v in self.__dict__.items() if v is not None}

    class BomCreate(MaterialCreate): pass
    class BomUpdate(MaterialUpdate): pass
    class WorkCenterCreate(MaterialCreate): pass
    class WorkCenterUpdate(MaterialUpdate): pass
    class ProcessCreate(MaterialCreate): pass
    class ProcessUpdate(MaterialUpdate): pass
    class RouteCreate(MaterialCreate): pass
    class RouteUpdate(MaterialUpdate): pass


class MaterialService:
    model = "material"
    @staticmethod
    async def get_by_id(material_id: int) -> Optional[Material]:
        return await Material.filter(id=material_id).first()

    @staticmethod
    async def get_by_code(material_code: str) -> Optional[Material]:
        return await Material.filter(material_code=material_code).first()

    @staticmethod
    async def create_material(data: MaterialCreate) -> Material:
        if await MaterialService.check_code_exists(data.material_code):
            raise ValueError("物料编码已存在")
        
        material_data = data.__dict__.copy()
        
        # 如果没有提供product_id，尝试从产品模块查询
        if not material_data.get('product_id') and PRODUCT_AVAILABLE and Product is not None:
            product = await Product.filter(name=data.material_code).first()
            if product:
                material_data['product_id'] = product.id
        
        return await Material.create(**material_data)

    @staticmethod
    async def update_material(material_id: int, data: MaterialUpdate) -> Optional[Material]:
        material = await Material.filter(id=material_id).first()
        if not material:
            return None
        if data.material_code and data.material_code != material.material_code:
            if await MaterialService.check_code_exists(data.material_code, exclude_id=material_id):
                raise ValueError("物料编码已被使用")
        update_data = data.model_dump(exclude_none=True)
        await material.update_from_dict(update_data).save()
        return material

    @staticmethod
    async def delete_material(material_id: int) -> bool:
        deleted_count = await Material.filter(id=material_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        material_code: Optional[str] = None,
        material_name: Optional[str] = None,
        material_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Tuple[List[Material], int]:
        query = Material.all()
        if material_code:
            query = query.filter(material_code__icontains=material_code)
        if material_name:
            query = query.filter(material_name__icontains=material_name)
        if material_type:
            query = query.filter(material_type=material_type)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = Material.filter(material_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class BomService:
    model = "bom"
    @staticmethod
    async def get_by_id(bom_id: int) -> Optional[Bom]:
        return await Bom.filter(id=bom_id).first()

    @staticmethod
    async def create_bom(data: BomCreate) -> Bom:
        bom_data = data.__dict__.copy()
        
        # 如果没有提供product_id，尝试从产品模块查询成品
        if not bom_data.get('product_id') and PRODUCT_AVAILABLE and Product is not None:
            product = await Product.filter(name=data.product_code).first()
            if product:
                bom_data['product_id'] = product.id
        
        # 如果没有提供item_id，尝试从产品模块查询物料
        if not bom_data.get('item_id') and PRODUCT_AVAILABLE and Product is not None:
            item = await Product.filter(name=data.item_code).first()
            if item:
                bom_data['item_id'] = item.id
        
        return await Bom.create(**bom_data)

    @staticmethod
    async def update_bom(bom_id: int, data: BomUpdate) -> Optional[Bom]:
        bom = await Bom.filter(id=bom_id).first()
        if not bom:
            return None
        update_data = data.model_dump(exclude_none=True)
        await bom.update_from_dict(update_data).save()
        return bom

    @staticmethod
    async def delete_bom(bom_id: int) -> bool:
        deleted_count = await Bom.filter(id=bom_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        product_code: Optional[str] = None,
        item_code: Optional[str] = None,
        version: Optional[str] = None
    ) -> Tuple[List[Bom], int]:
        query = Bom.all()
        if product_code:
            query = query.filter(product_code__icontains=product_code)
        if item_code:
            query = query.filter(item_code__icontains=item_code)
        if version:
            query = query.filter(version=version)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def get_bom_by_product(product_code: str, version: Optional[str] = None) -> List[Bom]:
        """获取产品的BOM列表（单层）"""
        query = Bom.filter(product_code=product_code, is_active=True)
        if version:
            query = query.filter(version=version)
        return await query.order_by('level', 'item_code')

    @staticmethod
    async def get_multi_level_bom(
        product_code: str, 
        version: Optional[str] = None,
        max_level: int = 10,
        current_level: int = 1
    ) -> List[Dict[str, Any]]:
        """递归获取多级BOM结构
        
        Args:
            product_code: 成品编码
            version: BOM版本号
            max_level: 最大递归层级
            current_level: 当前层级（内部使用）
        
        Returns:
            多级BOM树形结构列表
        """
        if current_level > max_level:
            return []

        boms = await BomService.get_bom_by_product(product_code, version)
        result = []

        for bom in boms:
            item_dict = {
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
                "children": []
            }

            # 递归查询子级BOM（如果当前物料也是某个产品的子项）
            children = await BomService.get_multi_level_bom(
                product_code=bom.item_code,
                version=version,
                max_level=max_level,
                current_level=current_level + 1
            )
            
            if children:
                item_dict["children"] = children

            result.append(item_dict)

        return result

    @staticmethod
    async def get_flattened_bom(
        product_code: str,
        version: Optional[str] = None,
        max_level: int = 10,
        parent_quantity: Decimal = None
    ) -> List[Dict[str, Any]]:
        """扁平化展开多级BOM（汇总所有物料需求）
        
        Args:
            product_code: 成品编码
            version: BOM版本号
            max_level: 最大递归层级
            parent_quantity: 父项数量（内部使用）
        
        Returns:
            扁平化的BOM列表，包含累计用量
        """
        if parent_quantity is None:
            parent_quantity = Decimal("1")

        boms = await BomService.get_bom_by_product(product_code, version)
        result = []

        for bom in boms:
            # 计算累计用量（考虑损耗率）
            base_quantity = bom.quantity * parent_quantity
            scrap_quantity = base_quantity * bom.scrap_rate
            total_quantity = base_quantity + scrap_quantity

            item_dict = {
                "id": bom.id,
                "product_code": bom.product_code,
                "product_name": bom.product_name,
                "version": bom.version,
                "level": bom.level,
                "parent_item_code": bom.parent_item_code,
                "item_code": bom.item_code,
                "item_name": bom.item_name,
                "unit_quantity": float(bom.quantity) if bom.quantity and hasattr(bom.quantity, "__float__") else bom.quantity,
                "parent_quantity": float(parent_quantity) if parent_quantity and hasattr(parent_quantity, "__float__") else parent_quantity,
                "scrap_rate": float(bom.scrap_rate) if bom.scrap_rate and hasattr(bom.scrap_rate, "__float__") else bom.scrap_rate,
                "scrap_quantity": float(scrap_quantity) if scrap_quantity and hasattr(scrap_quantity, "__float__") else scrap_quantity,
                "total_quantity": float(total_quantity) if total_quantity and hasattr(total_quantity, "__float__") else total_quantity,
                "unit": bom.unit,
                "remark": bom.remark,
                "is_active": bom.is_active,
            }

            result.append(item_dict)

            # 递归查询子级BOM
            if max_level > 1:
                children = await BomService.get_flattened_bom(
                    product_code=bom.item_code,
                    version=version,
                    max_level=max_level - 1,
                    parent_quantity=total_quantity
                )
                result.extend(children)

        return result

    @staticmethod
    async def calculate_mrp(
        product_code: str,
        demand_quantity: Decimal,
        version: Optional[str] = None,
        max_level: int = 10
    ) -> Dict[str, Any]:
        """物料需求计划(MRP)计算
        
        根据需求数量计算所需的所有物料及其数量
        
        Args:
            product_code: 成品编码
            demand_quantity: 需求数量
            version: BOM版本号
            max_level: 最大递归层级
        
        Returns:
            MRP计算结果，包含物料需求汇总
        """
        flattened_bom = await BomService.get_flattened_bom(
            product_code=product_code,
            version=version,
            max_level=max_level,
            parent_quantity=demand_quantity
        )

        # 汇总相同物料的需求
        material_summary = {}
        for item in flattened_bom:
            key = item["item_code"]
            if key not in material_summary:
                material_summary[key] = {
                    "item_code": item["item_code"],
                    "item_name": item["item_name"],
                    "total_quantity": Decimal("0"),
                    "unit": item["unit"],
                    "occurrences": []
                }
            material_summary[key]["total_quantity"] += Decimal(str(item["total_quantity"]))
            material_summary[key]["occurrences"].append({
                "level": item["level"],
                "parent_product": item["product_code"],
                "quantity": item["total_quantity"]
            })

        return {
            "product_code": product_code,
            "demand_quantity": float(demand_quantity) if demand_quantity and hasattr(demand_quantity, "__float__") else demand_quantity,
            "version": version or "latest",
            "total_items": len(flattened_bom),
            "unique_materials": len(material_summary),
            "detailed_bom": flattened_bom,
            "material_summary": list(material_summary.values())
        }


class BomVersionService:
    model = "bom_version"
    @staticmethod
    async def get_by_id(version_id: int) -> Optional[BomVersion]:
        return await BomVersion.filter(id=version_id).first()

    @staticmethod
    async def get_by_product_and_version(product_code: str, version: str) -> Optional[BomVersion]:
        return await BomVersion.filter(product_code=product_code, version=version).first()

    @staticmethod
    async def get_active_version(product_code: str) -> Optional[BomVersion]:
        return await BomVersion.filter(product_code=product_code, status="active").first()

    @staticmethod
    async def get_version_history(product_code: str) -> List[BomVersion]:
        return await BomVersion.filter(product_code=product_code).order_by('-created_at')

    @staticmethod
    async def create_version(product_code: str, version: str, product_name: str = "", **kwargs) -> BomVersion:
        if await BomVersionService.get_by_product_and_version(product_code, version):
            raise ValueError(f"版本 {version} 已存在")
        
        return await BomVersion.create(
            product_code=product_code,
            version=version,
            product_name=product_name,
            status="draft",
            **kwargs
        )

    @staticmethod
    async def copy_version(source_version_id: int, new_version: str) -> BomVersion:
        source_version = await BomVersionService.get_by_id(source_version_id)
        if not source_version:
            raise ValueError("源版本不存在")
        
        if await BomVersionService.get_by_product_and_version(source_version.product_code, new_version):
            raise ValueError(f"版本 {new_version} 已存在")
        
        new_version_obj = await BomVersion.create(
            product_code=source_version.product_code,
            version=new_version,
            product_name=source_version.product_name,
            status="draft",
            description=f"复制自版本 {source_version.version}",
            ecn_code=source_version.ecn_code
        )
        
        source_boms = await Bom.filter(product_code=source_version.product_code, version=source_version.version)
        for bom in source_boms:
            await Bom.create(
                product_id=bom.product_id,
                product_code=bom.product_code,
                product_name=bom.product_name,
                version=new_version,
                level=bom.level,
                parent_item_code=bom.parent_item_code,
                item_id=bom.item_id,
                item_code=bom.item_code,
                item_name=bom.item_name,
                quantity=bom.quantity,
                unit=bom.unit,
                scrap_rate=bom.scrap_rate,
                drawing_code=bom.drawing_code,
                drawing_url=bom.drawing_url,
                remark=bom.remark,
                is_active=bom.is_active
            )
        
        return new_version_obj

    @staticmethod
    async def activate_version(version_id: int) -> Optional[BomVersion]:
        version = await BomVersionService.get_by_id(version_id)
        if not version:
            return None
        
        if version.status == "active":
            raise ValueError("版本已经是生效状态")
        
        active_version = await BomVersionService.get_active_version(version.product_code)
        if active_version:
            active_version.status = "obsolete"
            await active_version.save()
        
        version.status = "active"
        from datetime import date
        version.effective_date = date.today()
        await version.save()
        
        return version

    @staticmethod
    async def obsolete_version(version_id: int) -> Optional[BomVersion]:
        version = await BomVersionService.get_by_id(version_id)
        if not version:
            return None
        
        if version.status == "obsolete":
            raise ValueError("版本已经是作废状态")
        
        version.status = "obsolete"
        await version.save()
        
        return version

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        product_code: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[List[BomVersion], int]:
        query = BomVersion.all()
        if product_code:
            query = query.filter(product_code__icontains=product_code)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total


class WorkCenterService:
    model = "work_center"
    @staticmethod
    async def get_by_id(wc_id: int) -> Optional[WorkCenter]:
        return await WorkCenter.filter(id=wc_id).first()

    @staticmethod
    async def get_by_code(wc_code: str) -> Optional[WorkCenter]:
        return await WorkCenter.filter(work_center_code=wc_code).first()

    @staticmethod
    async def create_work_center(data: WorkCenterCreate) -> WorkCenter:
        if await WorkCenterService.check_code_exists(data.work_center_code):
            raise ValueError("工作中心编码已存在")
        return await WorkCenter.create(**data.__dict__)

    @staticmethod
    async def update_work_center(wc_id: int, data: WorkCenterUpdate) -> Optional[WorkCenter]:
        wc = await WorkCenter.filter(id=wc_id).first()
        if not wc:
            return None
        if data.work_center_code and data.work_center_code != wc.work_center_code:
            if await WorkCenterService.check_code_exists(data.work_center_code, exclude_id=wc_id):
                raise ValueError("工作中心编码已被使用")
        update_data = data.model_dump(exclude_none=True)
        await wc.update_from_dict(update_data).save()
        return wc

    @staticmethod
    async def delete_work_center(wc_id: int) -> bool:
        deleted_count = await WorkCenter.filter(id=wc_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        work_center_code: Optional[str] = None,
        work_center_name: Optional[str] = None,
        department: Optional[str] = None
    ) -> Tuple[List[WorkCenter], int]:
        query = WorkCenter.all()
        if work_center_code:
            query = query.filter(work_center_code__icontains=work_center_code)
        if work_center_name:
            query = query.filter(work_center_name__icontains=work_center_name)
        if department:
            query = query.filter(department=department)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = WorkCenter.filter(work_center_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class ProcessService:
    model = "process"
    @staticmethod
    async def get_by_id(process_id: int) -> Optional[Process]:
        return await Process.filter(id=process_id).first()

    @staticmethod
    async def get_by_code(process_code: str) -> Optional[Process]:
        return await Process.filter(process_code=process_code).first()

    @staticmethod
    async def create_process(data: ProcessCreate) -> Process:
        if await ProcessService.check_code_exists(data.process_code):
            raise ValueError("工序编码已存在")
        return await Process.create(**data.__dict__)

    @staticmethod
    async def update_process(process_id: int, data: ProcessUpdate) -> Optional[Process]:
        process = await Process.filter(id=process_id).first()
        if not process:
            return None
        if data.process_code and data.process_code != process.process_code:
            if await ProcessService.check_code_exists(data.process_code, exclude_id=process_id):
                raise ValueError("工序编码已被使用")
        update_data = data.model_dump(exclude_none=True)
        await process.update_from_dict(update_data).save()
        return process

    @staticmethod
    async def delete_process(process_id: int) -> bool:
        deleted_count = await Process.filter(id=process_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        process_code: Optional[str] = None,
        process_name: Optional[str] = None,
        work_center_code: Optional[str] = None
    ) -> Tuple[List[Process], int]:
        query = Process.all()
        if process_code:
            query = query.filter(process_code__icontains=process_code)
        if process_name:
            query = query.filter(process_name__icontains=process_name)
        if work_center_code:
            query = query.filter(work_center_code=work_center_code)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('sequence', '-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = Process.filter(process_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class RouteService:
    model = "route"
    @staticmethod
    async def get_by_id(route_id: int) -> Optional[Route]:
        return await Route.filter(id=route_id).first()

    @staticmethod
    async def get_by_code(route_code: str) -> Optional[Route]:
        return await Route.filter(route_code=route_code).first()

    @staticmethod
    async def get_route_with_processes(route_id: int) -> Optional[dict]:
        route = await Route.filter(id=route_id).first()
        if not route:
            return None
        route_dict = await route.to_dict()
        processes = await RouteProcess.filter(route_code=route.route_code).order_by('sequence')
        route_dict['processes'] = [await p.to_dict() for p in processes]
        return route_dict

    @staticmethod
    async def create_route(data: RouteCreate) -> Route:
        if await RouteService.check_code_exists(data.route_code):
            raise ValueError("路线编码已存在")
        
        route_data = data.__dict__.copy()
        processes_data = route_data.pop('processes', [])
        
        route = await Route.create(**route_data)
        
        for seq, process in enumerate(processes_data, 1):
            await RouteProcess.create(
                route_code=route.route_code,
                process_code=process.get('process_code', ''),
                process_name=process.get('process_name', ''),
                sequence=process.get('sequence', seq),
                work_center_code=process.get('work_center_code'),
                work_center_name=process.get('work_center_name')
            )
        
        return route

    @staticmethod
    async def update_route(route_id: int, data: RouteUpdate) -> Optional[Route]:
        route = await Route.filter(id=route_id).first()
        if not route:
            return None
        
        old_code = route.route_code
        
        if data.route_code and data.route_code != old_code:
            if await RouteService.check_code_exists(data.route_code, exclude_id=route_id):
                raise ValueError("路线编码已被使用")
        
        update_data = data.model_dump(exclude_none=True)
        processes_data = update_data.pop('processes', None)
        
        await route.update_from_dict(update_data).save()
        
        if processes_data is not None:
            await RouteProcess.filter(route_code=old_code).delete()
            new_code = update_data.get('route_code', old_code)
            for seq, process in enumerate(processes_data, 1):
                await RouteProcess.create(
                    route_code=new_code,
                    process_code=process.get('process_code', ''),
                    process_name=process.get('process_name', ''),
                    sequence=process.get('sequence', seq),
                    work_center_code=process.get('work_center_code'),
                    work_center_name=process.get('work_center_name')
                )
        
        return route

    @staticmethod
    async def delete_route(route_id: int) -> bool:
        route = await Route.filter(id=route_id).first()
        if not route:
            return False
        
        await RouteProcess.filter(route_code=route.route_code).delete()
        await Route.filter(id=route_id).delete()
        return True

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        route_code: Optional[str] = None,
        route_name: Optional[str] = None,
        product_code: Optional[str] = None,
        bom_code: Optional[str] = None
    ) -> Tuple[List[Route], int]:
        query = Route.all()
        if route_code:
            query = query.filter(route_code__icontains=route_code)
        if route_name:
            query = query.filter(route_name__icontains=route_name)
        if product_code:
            query = query.filter(product_code__icontains=product_code)
        if bom_code:
            query = query.filter(bom_code__icontains=bom_code)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = Route.filter(route_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()