from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.equipment.services.equipment_service import EquipmentFaultService
    from base.plugins.equipment.schemas.equipment_schema import (
        EquipmentFaultCreate, EquipmentFaultUpdate, EquipmentFaultResponse,
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

    class EquipmentFaultService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def create_fault(data):
            return None
        @staticmethod
        async def update_fault(id, data):
            return None
        @staticmethod
        async def delete_fault(id):
            return False
        @staticmethod
        async def process_fault(id, operator=None):
            return None
        @staticmethod
        async def resolve_fault(id, solution, operator=None):
            return None
        @staticmethod
        async def close_fault(id):
            return None
        @staticmethod
        async def get_list(**kwargs):
            return [], 0

    class EquipmentFaultCreate(BaseModel): pass
    class EquipmentFaultUpdate(BaseModel): pass
    class EquipmentFaultResponse(BaseModel): pass
    class ListResponse(BaseModel): pass

fault_router = APIRouter(prefix="/fault", tags=["设备故障"])

@fault_router.get("/{fault_id}", summary="获取故障单详情")
async def get_fault(fault_id: int):
    fault = await EquipmentFaultService.get_by_id(fault_id)
    if not fault:
        raise HTTPException(status_code=404, detail="故障单不存在")
    return success_response(data=fault)

@fault_router.post("/", summary="创建故障单")
async def create_fault(data: EquipmentFaultCreate):
    try:
        fault = await EquipmentFaultService.create_fault(data)
        return success_response(data=fault)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fault_router.put("/{fault_id}", summary="更新故障单")
async def update_fault(fault_id: int, data: EquipmentFaultUpdate):
    fault = await EquipmentFaultService.update_fault(fault_id, data)
    if not fault:
        raise HTTPException(status_code=404, detail="故障单不存在")
    return success_response(data=fault)

@fault_router.delete("/{fault_id}", summary="删除故障单")
async def delete_fault(fault_id: int):
    success = await EquipmentFaultService.delete_fault(fault_id)
    if not success:
        raise HTTPException(status_code=404, detail="故障单不存在")
    return success_response(data={"message": "故障单删除成功"}, msg="故障单删除成功")

@fault_router.post("/{fault_id}/process", summary="处理故障")
async def process_fault(fault_id: int, operator: Optional[str] = None):
    try:
        fault = await EquipmentFaultService.process_fault(fault_id, operator)
        if not fault:
            raise HTTPException(status_code=404, detail="故障单不存在")
        return success_response(data=fault)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fault_router.post("/{fault_id}/resolve", summary="解决故障")
async def resolve_fault(fault_id: int, solution: str, operator: Optional[str] = None):
    try:
        fault = await EquipmentFaultService.resolve_fault(fault_id, solution, operator)
        if not fault:
            raise HTTPException(status_code=404, detail="故障单不存在")
        return success_response(data=fault)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fault_router.post("/{fault_id}/close", summary="关闭故障")
async def close_fault(fault_id: int):
    try:
        fault = await EquipmentFaultService.close_fault(fault_id)
        if not fault:
            raise HTTPException(status_code=404, detail="故障单不存在")
        return success_response(data=fault)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@fault_router.get("/", summary="获取故障单列表")
async def list_fault(
    page: int = 1,
    page_size: int = 10,
    fault_code: Optional[str] = None,
    equipment_code: Optional[str] = None,
    fault_level: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await EquipmentFaultService.get_list(
        page=page, page_size=page_size,
        fault_code=fault_code,
        equipment_code=equipment_code,
        fault_level=fault_level,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})