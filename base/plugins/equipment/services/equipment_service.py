from typing import Optional, List, Tuple, Dict, Any
from decimal import Decimal
from tortoise.expressions import Q
try:
    from base.plugins.equipment.models.equipment import Equipment, EquipmentMaintenance, EquipmentFault
    from base.plugins.equipment.schemas.equipment_schema import (
        EquipmentCreate, EquipmentUpdate,
        EquipmentMaintenanceCreate, EquipmentMaintenanceUpdate,
        EquipmentFaultCreate, EquipmentFaultUpdate,
    )
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

    class Equipment(BaseModelMock):
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

    class EquipmentMaintenance(Equipment):
        pass

    class EquipmentFault(Equipment):
        pass

    class EquipmentCreate:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class EquipmentUpdate(EquipmentCreate):
        def model_dump(self, exclude_none=False):
            return {k: v for k, v in self.__dict__.items() if v is not None}

    class EquipmentMaintenanceCreate(EquipmentCreate):
        pass

    class EquipmentMaintenanceUpdate(EquipmentUpdate):
        pass

    class EquipmentFaultCreate(EquipmentCreate):
        pass

    class EquipmentFaultUpdate(EquipmentUpdate):
        pass


class EquipmentService:
    model = "equipment"
    @staticmethod
    async def get_by_id(equipment_id: int) -> Optional[Equipment]:
        return await Equipment.filter(id=equipment_id).first()

    @staticmethod
    async def get_by_code(equipment_code: str) -> Optional[Equipment]:
        return await Equipment.filter(equipment_code=equipment_code).first()

    @staticmethod
    async def create_equipment(data: EquipmentCreate) -> Equipment:
        if await EquipmentService.check_code_exists(data.equipment_code):
            raise ValueError("设备编码已存在")
        return await Equipment.create(**data.__dict__)

    @staticmethod
    async def update_equipment(equipment_id: int, data: EquipmentUpdate) -> Optional[Equipment]:
        equipment = await Equipment.filter(id=equipment_id).first()
        if not equipment:
            return None
        if data.equipment_code and data.equipment_code != equipment.equipment_code:
            if await EquipmentService.check_code_exists(data.equipment_code, exclude_id=equipment_id):
                raise ValueError("设备编码已被使用")
        update_data = data.model_dump(exclude_none=True)
        await equipment.update_from_dict(update_data).save()
        return equipment

    @staticmethod
    async def delete_equipment(equipment_id: int) -> bool:
        deleted_count = await Equipment.filter(id=equipment_id).delete()
        return deleted_count > 0

    @staticmethod
    async def change_status(equipment_id: int, status: str) -> Optional[Equipment]:
        equipment = await Equipment.filter(id=equipment_id).first()
        if not equipment:
            return None
        equipment.status = status
        await equipment.save()
        return equipment

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        equipment_code: Optional[str] = None,
        equipment_name: Optional[str] = None,
        equipment_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[List[Equipment], int]:
        query = Equipment.all()
        if equipment_code:
            query = query.filter(equipment_code__icontains=equipment_code)
        if equipment_name:
            query = query.filter(equipment_name__icontains=equipment_name)
        if equipment_type:
            query = query.filter(equipment_type=equipment_type)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = Equipment.filter(equipment_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class EquipmentMaintenanceService:
    model = "equipment_maintenance"
    @staticmethod
    async def get_by_id(maintenance_id: int) -> Optional[EquipmentMaintenance]:
        return await EquipmentMaintenance.filter(id=maintenance_id).first()

    @staticmethod
    async def get_by_code(maintenance_code: str) -> Optional[EquipmentMaintenance]:
        return await EquipmentMaintenance.filter(maintenance_code=maintenance_code).first()

    @staticmethod
    async def create_maintenance(data: EquipmentMaintenanceCreate) -> EquipmentMaintenance:
        if await EquipmentMaintenanceService.check_code_exists(data.maintenance_code):
            raise ValueError("保养单号已存在")
        return await EquipmentMaintenance.create(**data.__dict__)

    @staticmethod
    async def update_maintenance(maintenance_id: int, data: EquipmentMaintenanceUpdate) -> Optional[EquipmentMaintenance]:
        maintenance = await EquipmentMaintenance.filter(id=maintenance_id).first()
        if not maintenance:
            return None
        update_data = data.model_dump(exclude_none=True)
        await maintenance.update_from_dict(update_data).save()
        return maintenance

    @staticmethod
    async def delete_maintenance(maintenance_id: int) -> bool:
        deleted_count = await EquipmentMaintenance.filter(id=maintenance_id).delete()
        return deleted_count > 0

    @staticmethod
    async def complete_maintenance(maintenance_id: int, operator: str = None) -> Optional[EquipmentMaintenance]:
        maintenance = await EquipmentMaintenance.filter(id=maintenance_id).first()
        if not maintenance:
            return None
        if maintenance.status != "pending":
            raise ValueError(f"保养单当前状态为{maintenance.status}，无法完成")
        maintenance.status = "completed"
        maintenance.operator = operator
        await maintenance.save()
        return maintenance

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        maintenance_code: Optional[str] = None,
        equipment_code: Optional[str] = None,
        maintenance_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[List[EquipmentMaintenance], int]:
        query = EquipmentMaintenance.all()
        if maintenance_code:
            query = query.filter(maintenance_code__icontains=maintenance_code)
        if equipment_code:
            query = query.filter(equipment_code__icontains=equipment_code)
        if maintenance_type:
            query = query.filter(maintenance_type=maintenance_type)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = EquipmentMaintenance.filter(maintenance_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()


class EquipmentFaultService:
    model = "equipment_fault"
    @staticmethod
    async def get_by_id(fault_id: int) -> Optional[EquipmentFault]:
        return await EquipmentFault.filter(id=fault_id).first()

    @staticmethod
    async def get_by_code(fault_code: str) -> Optional[EquipmentFault]:
        return await EquipmentFault.filter(fault_code=fault_code).first()

    @staticmethod
    async def create_fault(data: EquipmentFaultCreate) -> EquipmentFault:
        if await EquipmentFaultService.check_code_exists(data.fault_code):
            raise ValueError("故障单号已存在")
        return await EquipmentFault.create(**data.__dict__)

    @staticmethod
    async def update_fault(fault_id: int, data: EquipmentFaultUpdate) -> Optional[EquipmentFault]:
        fault = await EquipmentFault.filter(id=fault_id).first()
        if not fault:
            return None
        update_data = data.model_dump(exclude_none=True)
        await fault.update_from_dict(update_data).save()
        return fault

    @staticmethod
    async def delete_fault(fault_id: int) -> bool:
        deleted_count = await EquipmentFault.filter(id=fault_id).delete()
        return deleted_count > 0

    @staticmethod
    async def process_fault(fault_id: int, operator: str = None) -> Optional[EquipmentFault]:
        fault = await EquipmentFault.filter(id=fault_id).first()
        if not fault:
            return None
        if fault.status != "open":
            raise ValueError(f"故障单当前状态为{fault.status}，无法处理")
        fault.status = "processing"
        fault.operator = operator
        await fault.save()
        return fault

    @staticmethod
    async def resolve_fault(fault_id: int, solution: str, operator: str = None) -> Optional[EquipmentFault]:
        fault = await EquipmentFault.filter(id=fault_id).first()
        if not fault:
            return None
        if fault.status != "processing":
            raise ValueError(f"故障单当前状态为{fault.status}，无法解决")
        fault.status = "resolved"
        fault.solution = solution
        fault.operator = operator
        await fault.save()
        return fault

    @staticmethod
    async def close_fault(fault_id: int) -> Optional[EquipmentFault]:
        fault = await EquipmentFault.filter(id=fault_id).first()
        if not fault:
            return None
        if fault.status != "resolved":
            raise ValueError(f"故障单当前状态为{fault.status}，无法关闭")
        fault.status = "closed"
        await fault.save()
        return fault

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        fault_code: Optional[str] = None,
        equipment_code: Optional[str] = None,
        fault_level: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[List[EquipmentFault], int]:
        query = EquipmentFault.all()
        if fault_code:
            query = query.filter(fault_code__icontains=fault_code)
        if equipment_code:
            query = query.filter(equipment_code__icontains=equipment_code)
        if fault_level:
            query = query.filter(fault_level=fault_level)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        query = EquipmentFault.filter(fault_code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()