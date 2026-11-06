from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.equipment.services.equipment_service import EquipmentMaintenanceService
    from base.plugins.equipment.schemas.equipment_schema import (
        EquipmentMaintenanceCreate, EquipmentMaintenanceUpdate, EquipmentMaintenanceResponse,
        ListResponse
    )
    from base.common.response import success_response
except ImportError:
    class BaseModel:
        pass

    class APIRouter:
        def __init__(self, prefix="", tags=None):
            self.prefix = prefix
            self.tags = tags or []

        def get(self, path):
            def decorator(func):
                return func
            return decorator

        def post(self, path):
            def decorator(func):
                return func
            return decorator

        def put(self, path):
            def decorator(func):
                return func
            return decorator

        def delete(self, path):
            def decorator(func):
                return func
            return decorator

    class Depends:
        def __init__(self, func):
            pass

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            pass

    class EquipmentMaintenanceService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def create_maintenance(data):
            return None
        @staticmethod
        async def update_maintenance(id, data):
            return None
        @staticmethod
        async def delete_maintenance(id):
            return False
        @staticmethod
        async def complete_maintenance(id, operator=None):
            return None
        @staticmethod
        async def get_list(**kwargs):
            return [], 0

    class EquipmentMaintenanceCreate(BaseModel): pass
    class EquipmentMaintenanceUpdate(BaseModel): pass
    class EquipmentMaintenanceResponse(BaseModel): pass
    class ListResponse(BaseModel): pass

maintenance_router = APIRouter(prefix="/maintenance", tags=["设备保养"])

@maintenance_router.get("/{maintenance_id}", summary="获取保养单详情")
async def get_maintenance(maintenance_id: int):
    maintenance = await EquipmentMaintenanceService.get_by_id(maintenance_id)
    if not maintenance:
        raise HTTPException(status_code=404, detail="保养单不存在")
    return success_response(data=maintenance)

@maintenance_router.post("/", summary="创建保养单")
async def create_maintenance(data: EquipmentMaintenanceCreate):
    try:
        maintenance = await EquipmentMaintenanceService.create_maintenance(data)
        return success_response(data=maintenance)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@maintenance_router.put("/{maintenance_id}", summary="更新保养单")
async def update_maintenance(maintenance_id: int, data: EquipmentMaintenanceUpdate):
    maintenance = await EquipmentMaintenanceService.update_maintenance(maintenance_id, data)
    if not maintenance:
        raise HTTPException(status_code=404, detail="保养单不存在")
    return success_response(data=maintenance)

@maintenance_router.delete("/{maintenance_id}", summary="删除保养单")
async def delete_maintenance(maintenance_id: int):
    success = await EquipmentMaintenanceService.delete_maintenance(maintenance_id)
    if not success:
        raise HTTPException(status_code=404, detail="保养单不存在")
    return success_response(data={"message": "保养单删除成功"}, msg="保养单删除成功")

@maintenance_router.post("/{maintenance_id}/complete", summary="完成保养")
async def complete_maintenance(maintenance_id: int, operator: Optional[str] = None):
    try:
        maintenance = await EquipmentMaintenanceService.complete_maintenance(maintenance_id, operator)
        if not maintenance:
            raise HTTPException(status_code=404, detail="保养单不存在")
        return success_response(data=maintenance)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@maintenance_router.get("/", summary="获取保养单列表")
async def list_maintenance(
    page: int = 1,
    page_size: int = 10,
    maintenance_code: Optional[str] = None,
    equipment_code: Optional[str] = None,
    maintenance_type: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await EquipmentMaintenanceService.get_list(
        page=page, page_size=page_size,
        maintenance_code=maintenance_code,
        equipment_code=equipment_code,
        maintenance_type=maintenance_type,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})