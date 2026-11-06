from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.equipment.services.equipment_service import EquipmentService
    from base.plugins.equipment.schemas.equipment_schema import (
        EquipmentCreate, EquipmentUpdate, EquipmentResponse,
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

    class EquipmentService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def create_equipment(data):
            return None
        @staticmethod
        async def update_equipment(id, data):
            return None
        @staticmethod
        async def delete_equipment(id):
            return False
        @staticmethod
        async def change_status(id, status):
            return None
        @staticmethod
        async def get_list(**kwargs):
            return [], 0

    class EquipmentCreate(BaseModel): pass
    class EquipmentUpdate(BaseModel): pass
    class EquipmentResponse(BaseModel): pass
    class ListResponse(BaseModel): pass

equipment_router = APIRouter(prefix="/equipment", tags=["设备台账"])

@equipment_router.get("/{equipment_id}", summary="获取设备详情")
async def get_equipment(equipment_id: int):
    equipment = await EquipmentService.get_by_id(equipment_id)
    if not equipment:
        raise HTTPException(status_code=404, detail="设备不存在")
    return success_response(data=equipment)

@equipment_router.post("/", summary="创建设备")
async def create_equipment(data: EquipmentCreate):
    try:
        equipment = await EquipmentService.create_equipment(data)
        return success_response(data=equipment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@equipment_router.put("/{equipment_id}", summary="更新设备")
async def update_equipment(equipment_id: int, data: EquipmentUpdate):
    try:
        equipment = await EquipmentService.update_equipment(equipment_id, data)
        if not equipment:
            raise HTTPException(status_code=404, detail="设备不存在")
        return success_response(data=equipment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@equipment_router.delete("/{equipment_id}", summary="删除设备")
async def delete_equipment(equipment_id: int):
    success = await EquipmentService.delete_equipment(equipment_id)
    if not success:
        raise HTTPException(status_code=404, detail="设备不存在")
    return success_response(data={"message": "设备删除成功"}, msg="设备删除成功")

@equipment_router.post("/{equipment_id}/status", summary="变更设备状态")
async def change_equipment_status(equipment_id: int, status: str):
    equipment = await EquipmentService.change_status(equipment_id, status)
    if not equipment:
        raise HTTPException(status_code=404, detail="设备不存在")
    return success_response(data=equipment)

@equipment_router.get("/", summary="获取设备列表")
async def list_equipment(
    page: int = 1,
    page_size: int = 10,
    equipment_code: Optional[str] = None,
    equipment_name: Optional[str] = None,
    equipment_type: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await EquipmentService.get_list(
        page=page, page_size=page_size,
        equipment_code=equipment_code,
        equipment_name=equipment_name,
        equipment_type=equipment_type,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})