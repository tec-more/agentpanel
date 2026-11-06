from fastapi import APIRouter
from base.plugins.equipment.api.v1.equipment_router import equipment_router
from base.plugins.equipment.api.v1.maintenance_router import maintenance_router
from base.plugins.equipment.api.v1.fault_router import fault_router

equipment_v1_router = APIRouter()

equipment_v1_router.include_router(equipment_router, prefix="/equipment", tags=["设备台账"])
equipment_v1_router.include_router(maintenance_router, prefix="/maintenance", tags=["设备保养"])
equipment_v1_router.include_router(fault_router, prefix="/fault", tags=["设备故障"])