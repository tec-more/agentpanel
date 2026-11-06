from typing import Optional, List, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.quality.services.quality_service import QualityInspectionService
    from base.plugins.quality.schemas.quality_schema import (
        QualityInspectionCreate, QualityInspectionUpdate, QualityInspectionResponse,
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

    class QualityInspectionService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def create_inspection(data):
            return None
        @staticmethod
        async def update_inspection(id, data):
            return None
        @staticmethod
        async def delete_inspection(id):
            return False
        @staticmethod
        async def submit_inspection(id, qualified_qty, unqualified_qty, inspector=None, items=None):
            return None
        @staticmethod
        async def get_list(**kwargs):
            return [], 0

    class QualityInspectionCreate(BaseModel): pass
    class QualityInspectionUpdate(BaseModel): pass
    class QualityInspectionResponse(BaseModel): pass
    class ListResponse(BaseModel): pass

inspection_router = APIRouter(prefix="/inspections", tags=["检验管理"])

@inspection_router.get("/{inspection_id}", summary="获取检验单详情")
async def get_inspection(inspection_id: int):
    inspection = await QualityInspectionService.get_by_id(inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="检验单不存在")
    return success_response(data=inspection)

@inspection_router.post("/", summary="创建检验单")
async def create_inspection(data: QualityInspectionCreate):
    try:
        inspection = await QualityInspectionService.create_inspection(data)
        return success_response(data=inspection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@inspection_router.put("/{inspection_id}", summary="更新检验单")
async def update_inspection(inspection_id: int, data: QualityInspectionUpdate):
    inspection = await QualityInspectionService.update_inspection(inspection_id, data)
    if not inspection:
        raise HTTPException(status_code=404, detail="检验单不存在")
    return success_response(data=inspection)

@inspection_router.delete("/{inspection_id}", summary="删除检验单")
async def delete_inspection(inspection_id: int):
    success = await QualityInspectionService.delete_inspection(inspection_id)
    if not success:
        raise HTTPException(status_code=404, detail="检验单不存在")
    return success_response(data={"message": "检验单删除成功"}, msg="检验单删除成功")

@inspection_router.post("/{inspection_id}/submit", summary="提交检验结果")
async def submit_inspection(
    inspection_id: int,
    qualified_quantity: int,
    unqualified_quantity: int,
    inspector: Optional[str] = None,
    inspection_items: Optional[List[Dict[str, Any]]] = None
):
    try:
        inspection = await QualityInspectionService.submit_inspection(
            inspection_id, qualified_quantity, unqualified_quantity, inspector, inspection_items
        )
        if not inspection:
            raise HTTPException(status_code=404, detail="检验单不存在")
        return success_response(data=inspection)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@inspection_router.get("/", summary="获取检验单列表")
async def list_inspections(
    page: int = 1,
    page_size: int = 10,
    inspection_code: Optional[str] = None,
    inspection_type: Optional[str] = None,
    material_code: Optional[str] = None,
    inspection_result: Optional[str] = None
):
    items, total = await QualityInspectionService.get_list(
        page=page, page_size=page_size,
        inspection_code=inspection_code,
        inspection_type=inspection_type,
        material_code=material_code,
        inspection_result=inspection_result
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})