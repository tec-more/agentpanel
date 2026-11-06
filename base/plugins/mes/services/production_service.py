from typing import Optional, List, Tuple, Dict, Any
from decimal import Decimal
from datetime import datetime
from tortoise.expressions import Q
from loguru import logger
try:
    from base.common.events.event_bus import event_bus
except ImportError:
    event_bus = None

try:
    from base.plugins.mes.models.production import ManufacturingOrder, WorkOrder
    from base.plugins.mes.schemas.mes_schema import (
        ManufacturingOrderCreate, ManufacturingOrderUpdate,
        WorkOrderCreate, WorkOrderUpdate,
        StartWORequest, SuspendWORequest, ResumeWORequest,
    )
    try:
        from base.plugins.mes.models.base_data import Bom, Route, RouteProcess
        BASE_DATA_AVAILABLE = True
    except ImportError:
        Bom = None
        Route = None
        RouteProcess = None
        BASE_DATA_AVAILABLE = False
    try:
        from base.plugins.equipment.models.equipment import Equipment
        EQUIPMENT_AVAILABLE = True
    except ImportError:
        Equipment = None
        EQUIPMENT_AVAILABLE = False
    try:
        from base.plugins.mes.services.kit_check_service import KitCheckService
        KIT_CHECK_AVAILABLE = True
    except ImportError:
        KitCheckService = None
        KIT_CHECK_AVAILABLE = False
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

    class ManufacturingOrder(BaseModelMock):
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
            return MockQuerySet()

        async def to_dict(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    class WorkOrder(ManufacturingOrder): pass

    class ManufacturingOrderCreate:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class ManufacturingOrderUpdate(ManufacturingOrderCreate):
        def model_dump(self, exclude_none=False):
            return {k: v for k, v in self.__dict__.items() if v is not None}

    class WorkOrderCreate(ManufacturingOrderCreate): pass
    class WorkOrderUpdate(ManufacturingOrderUpdate): pass


class ManufacturingOrderService:
    model = "manufacturing_order"
    @staticmethod
    async def get_by_id(mo_id: int) -> Optional[ManufacturingOrder]:
        return await ManufacturingOrder.filter(id=mo_id).first()

    @staticmethod
    async def get_by_code(mo_code: str) -> Optional[ManufacturingOrder]:
        return await ManufacturingOrder.filter(mo_code=mo_code).first()

    @staticmethod
    async def create_mo(data: ManufacturingOrderCreate) -> ManufacturingOrder:
        if await ManufacturingOrderService.check_code_exists(data.mo_code):
            raise ValueError("制造单编码已存在")
        return await ManufacturingOrder.create(**data.__dict__)

    @staticmethod
    async def update_mo(mo_id: int, data: ManufacturingOrderUpdate) -> Optional[ManufacturingOrder]:
        mo = await ManufacturingOrder.filter(id=mo_id).first()
        if not mo:
            return None
        if data.mo_code and data.mo_code != mo.mo_code:
            if await ManufacturingOrderService.check_code_exists(data.mo_code, exclude_id=mo_id):
                raise ValueError("制造单编码已被使用")
        update_data = data.model_dump(exclude_none=True)
        await mo.update_from_dict(update_data).save()
        return mo

    @staticmethod
    async def delete_mo(mo_id: int) -> bool:
        deleted_count = await ManufacturingOrder.filter(id=mo_id).delete()
        return deleted_count > 0

    @staticmethod
    async def release_mo(mo_id: int, skip_kit_check: bool = False) -> Optional[ManufacturingOrder]:
        mo = await ManufacturingOrder.filter(id=mo_id).first()
        if not mo:
            return None
        if mo.status != "planned":
            raise ValueError(f"制造单当前状态为{mo.status}，无法下达")

        if BASE_DATA_AVAILABLE and Bom is not None:
            bom_exists = await Bom.filter(product_code=mo.product_code, is_active=True).exists()
            if not bom_exists:
                raise ValueError("产品BOM未维护或已失效，无法下达")

        if KIT_CHECK_AVAILABLE and KitCheckService is not None and not skip_kit_check:
            kit_result = await KitCheckService.check_kit_by_mo(mo_id)
            if "error" not in kit_result and kit_result.get("kit_status") != "full_kit":
                shortage_list = kit_result.get("shortage_list", [])
                shortage_info = "; ".join([f"{item['item_name']}({item['item_code']})缺{item['shortage']}{item['unit']}" for item in shortage_list])
                raise ValueError(f"物料不齐套，无法下达制造单。缺料清单: {shortage_info}")

        mo.status = "released"
        mo.actual_start_date = datetime.now()
        await mo.save()

        work_orders = await ManufacturingOrderService.generate_work_orders(mo_id)

        mo.barcode = f"MO-{mo.mo_code}"
        await mo.save()

        return mo

    @staticmethod
    async def complete_mo(mo_id: int) -> Optional[ManufacturingOrder]:
        mo = await ManufacturingOrder.filter(id=mo_id).first()
        if not mo:
            return None
        if mo.status not in ["released", "processing"]:
            raise ValueError(f"制造单当前状态为{mo.status}，无法完成")
        mo.status = "completed"
        await mo.save()
        return mo

    @staticmethod
    async def cancel_mo(mo_id: int) -> Optional[ManufacturingOrder]:
        mo = await ManufacturingOrder.filter(id=mo_id).first()
        if not mo:
            return None
        if mo.status == "completed":
            raise ValueError("已完成的制造单无法取消")
        mo.status = "canceled"
        await mo.save()
        return mo

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        mo_code: Optional[str] = None,
        product_code: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None
    ) -> Tuple[List[ManufacturingOrder], int]:
        query = ManufacturingOrder.all()
        if mo_code:
            query = query.filter(mo_code__icontains=mo_code)
        if product_code:
            query = query.filter(product_code__icontains=product_code)
        if status:
            query = query.filter(status=status)
        if priority:
            query = query.filter(priority=priority)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = ManufacturingOrder.filter(mo_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def generate_work_orders(mo_id: int) -> List[WorkOrder]:
        mo = await ManufacturingOrder.filter(id=mo_id).first()
        if not mo:
            raise ValueError("制造单不存在")
        if mo.status not in ["released", "processing"]:
            raise ValueError("只有已下发或生产中的制造单才能生成工单")

        try:
            from base.plugins.mes.models.base_data import Route, RouteProcess
            route = await Route.filter(product_code=mo.product_code).first()
        except ImportError:
            route = None

        work_orders = []
        route_processes = []
        if route:
            try:
                route_processes = await RouteProcess.filter(route_code=route.route_code).order_by('sequence')
            except Exception:
                route_processes = []

        if route_processes:
            for idx, detail in enumerate(route_processes):
                wo_code = f"WO-{mo.mo_code}-{idx + 1:03d}"
                wc_code = getattr(detail, 'work_center_code', None) or None
                wc_name = getattr(detail, 'work_center_name', None) or None
                wo_data = WorkOrderCreate(
                    wo_code=wo_code,
                    mo_code=mo.mo_code,
                    mo_name=mo.product_name,
                    product_code=mo.product_code,
                    product_name=mo.product_name,
                    process_code=getattr(detail, 'process_code', f'PROC-{idx + 1}'),
                    process_name=getattr(detail, 'process_name', f'工序{idx + 1}'),
                    work_center_code=wc_code,
                    work_center_name=wc_name,
                    quantity=mo.quantity,
                    planned_start_date=mo.planned_start_date,
                    planned_end_date=mo.planned_end_date,
                    remark=f"由制造单{mo.mo_code}自动生成"
                )
                wo = await WorkOrderService.create_wo(wo_data)
                work_orders.append(wo)
        else:
            wo_code = f"WO-{mo.mo_code}-001"
            wo_data = WorkOrderCreate(
                wo_code=wo_code,
                mo_code=mo.mo_code,
                mo_name=mo.product_name,
                product_code=mo.product_code,
                product_name=mo.product_name,
                process_code="PROC-001",
                process_name="默认工序",
                work_center_code=None,
                work_center_name=None,
                quantity=mo.quantity,
                planned_start_date=mo.planned_start_date,
                planned_end_date=mo.planned_end_date,
                remark=f"由制造单{mo.mo_code}自动生成"
            )
            wo = await WorkOrderService.create_wo(wo_data)
            work_orders.append(wo)

        return work_orders


class WorkOrderService:
    model = "work_order"
    @staticmethod
    async def get_by_id(wo_id: int) -> Optional[WorkOrder]:
        return await WorkOrder.filter(id=wo_id).first()

    @staticmethod
    async def get_by_code(wo_code: str) -> Optional[WorkOrder]:
        return await WorkOrder.filter(wo_code=wo_code).first()

    @staticmethod
    async def create_wo(data: WorkOrderCreate) -> WorkOrder:
        if await WorkOrderService.check_code_exists(data.wo_code):
            raise ValueError("工单编码已存在")
        return await WorkOrder.create(**data.__dict__)

    @staticmethod
    async def update_wo(wo_id: int, data: WorkOrderUpdate) -> Optional[WorkOrder]:
        wo = await WorkOrder.filter(id=wo_id).first()
        if not wo:
            return None
        if data.wo_code and data.wo_code != wo.wo_code:
            if await WorkOrderService.check_code_exists(data.wo_code, exclude_id=wo_id):
                raise ValueError("工单编码已被使用")
        update_data = data.model_dump(exclude_none=True)
        await wo.update_from_dict(update_data).save()
        return wo

    @staticmethod
    async def delete_wo(wo_id: int) -> bool:
        deleted_count = await WorkOrder.filter(id=wo_id).delete()
        return deleted_count > 0

    @staticmethod
    async def release_wo(wo_id: int) -> Optional[WorkOrder]:
        wo = await WorkOrder.filter(id=wo_id).first()
        if not wo:
            return None
        if wo.status != "pending":
            raise ValueError(f"工单当前状态为{wo.status}，无法下达")
        wo.status = "released"
        await wo.save()
        return wo

    @staticmethod
    async def start_wo(wo_id: int, data: StartWORequest = None) -> Optional[WorkOrder]:
        wo = await WorkOrder.filter(id=wo_id).first()
        if not wo:
            return None
        if wo.status not in ("released",):
            raise ValueError(f"工单当前状态为{wo.status}，无法开始")

        if data and data.equipment_code and EQUIPMENT_AVAILABLE and Equipment is not None:
            equip = await Equipment.filter(equipment_code=data.equipment_code).first()
            if not equip:
                raise ValueError(f"设备{data.equipment_code}不存在")
            if equip.status not in ("idle", "running"):
                raise ValueError(f"设备{data.equipment_code}状态为{equip.status}，无法开工")

        wo.status = "processing"
        wo.actual_start_date = datetime.now()
        if data:
            wo.operator = data.operator
            wo.equipment_code = data.equipment_code
            wo.shift_code = data.shift_code
        wo.barcode = f"WO-{wo.wo_code}"
        await wo.save()
        return wo

    @staticmethod
    async def suspend_wo(wo_id: int, data: SuspendWORequest = None) -> Optional[WorkOrder]:
        wo = await WorkOrder.filter(id=wo_id).first()
        if not wo:
            return None
        if wo.status != "processing":
            raise ValueError(f"工单当前状态为{wo.status}，无法暂停")
        wo.status = "suspended"
        if data:
            wo.suspend_reason = data.suspend_reason
            wo.suspend_source = data.suspend_source
        wo.suspended_at = datetime.now()
        await wo.save()
        return wo

    @staticmethod
    async def resume_wo(wo_id: int, data: ResumeWORequest = None) -> Optional[WorkOrder]:
        wo = await WorkOrder.filter(id=wo_id).first()
        if not wo:
            return None
        if wo.status != "suspended":
            raise ValueError(f"工单当前状态为{wo.status}，无法恢复")
        wo.status = "processing"
        wo.suspend_reason = None
        wo.suspend_source = None
        wo.suspended_at = None
        await wo.save()
        return wo

    @staticmethod
    async def complete_wo(wo_id: int, actual_quantity: int, scrap_quantity: int = 0) -> Optional[WorkOrder]:
        wo = await WorkOrder.filter(id=wo_id).first()
        if not wo:
            return None
        if wo.status != "processing":
            raise ValueError(f"工单当前状态为{wo.status}，无法完成")
        if actual_quantity <= 0 and scrap_quantity <= 0:
            raise ValueError("完工数量和报废数量不能同时为零或负数")
        if actual_quantity < 0:
            raise ValueError("完工数量不能为负数")
        if scrap_quantity < 0:
            raise ValueError("报废数量不能为负数")
        wo.status = "completed"
        wo.actual_quantity = actual_quantity
        wo.scrap_quantity = scrap_quantity
        await wo.save()

        if event_bus:
            try:
                await event_bus.publish(
                    "work_order.completed",
                    work_order_id=wo.id,
                    work_order_no=wo.wo_code,
                    mo_code=wo.mo_code,
                    product_id=getattr(wo, 'product_id', None),
                    product_code=wo.product_code,
                    product_name=wo.product_name,
                    completed_quantity=actual_quantity,
                    unit_cost=float(getattr(wo, 'unit_cost', 0) or 0),
                    created_by=getattr(wo, 'created_by', 'system'),
                )
            except Exception as e:
                logger.error(f"发布工单完工事件失败: {e}")

        return wo

    @staticmethod
    async def close_wo(wo_id: int) -> Optional[WorkOrder]:
        wo = await WorkOrder.filter(id=wo_id).first()
        if not wo:
            return None
        if wo.status != "completed":
            raise ValueError(f"工单当前状态为{wo.status}，无法关闭")
        wo.status = "closed"
        await wo.save()
        return wo

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        wo_code: Optional[str] = None,
        mo_code: Optional[str] = None,
        product_code: Optional[str] = None,
        status: Optional[str] = None,
        work_center_code: Optional[str] = None
    ) -> Tuple[List[WorkOrder], int]:
        query = WorkOrder.all()
        if wo_code:
            query = query.filter(wo_code__icontains=wo_code)
        if mo_code:
            query = query.filter(mo_code__icontains=mo_code)
        if product_code:
            query = query.filter(product_code__icontains=product_code)
        if status:
            query = query.filter(status=status)
        if work_center_code:
            query = query.filter(work_center_code=work_center_code)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = WorkOrder.filter(wo_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()