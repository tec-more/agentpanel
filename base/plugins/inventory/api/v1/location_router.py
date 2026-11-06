from typing import Optional
from fastapi import APIRouter, HTTPException, Query

try:
    from base.plugins.inventory.services.inventory_service import LocationService
    from base.plugins.inventory.schemas.inventory_schema import (
        StockLocationCreate, StockLocationUpdate, StockLocationResponse,
        ListResponse, MessageResponse
    )
    from base.common.response import success_response
except ImportError:
    class APIRouter:
        def __init__(self, prefix="", tags=None):
            self.prefix = prefix
            self.tags = tags or []

        def get(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

        def post(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

        def put(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

        def delete(self, path, response_model=None):
            def decorator(func):
                return func
            return decorator

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    class Query:
        def __init__(self, default=None, **kwargs):
            self.default = default

    class LocationService:
        @staticmethod
        async def get_by_id(id): return None
        @staticmethod
        async def create_location(data): return None
        @staticmethod
        async def update_location(id, data): return None
        @staticmethod
        async def delete_location(id): return False
        @staticmethod
        async def get_list(**kwargs): return [], 0
        @staticmethod
        async def get_tree(location_id=None): return []
        @staticmethod
        async def get_children(location_id): return []

    class StockLocationCreate: pass
    class StockLocationUpdate: pass
    class StockLocationResponse: pass
    class ListResponse: pass
    class MessageResponse: pass


location_router = APIRouter(prefix="/locations", tags=["库位管理"])


@location_router.get("/{location_id}", summary="获取库位详情")
async def get_location(location_id: int):
    """根据ID获取库位详情"""
    location = await LocationService.get_by_id(location_id)
    if not location:
        raise HTTPException(status_code=404, detail="库位不存在")
    return success_response(data=await location.to_dict())


@location_router.post("", summary="创建库位")
async def create_location(data: StockLocationCreate):
    """创建新库位，支持层级结构，自动生成完整名称和路径"""
    try:
        location = await LocationService.create_location(data)
        return success_response(data=await location.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@location_router.put("/{location_id}", summary="更新库位")
async def update_location(location_id: int, data: StockLocationUpdate):
    """更新库位信息"""
    try:
        location = await LocationService.update_location(location_id, data)
        if not location:
            raise HTTPException(status_code=404, detail="库位不存在")
        return success_response(data=await location.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@location_router.delete("/{location_id}", summary="删除库位")
async def delete_location(location_id: int):
    """删除库位（需无子库位和库存）"""
    try:
        success = await LocationService.delete_location(location_id)
        if not success:
            raise HTTPException(status_code=404, detail="库位不存在")
        return success_response(data={"message": "库位删除成功"}, msg="库位删除成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@location_router.get("", summary="获取库位列表")
async def list_locations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    location_code: Optional[str] = Query(None, description="库位编码"),
    location_name: Optional[str] = Query(None, description="库位名称"),
    parent_id: Optional[int] = Query(None, description="父库位ID"),
    warehouse_id: Optional[int] = Query(None, description="仓库ID"),
    warehouse_code: Optional[str] = Query(None, description="仓库编码"),
    location_type: Optional[str] = Query(None, description="库位类型"),
    usage: Optional[str] = Query(None, description="用途"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    """获取库位列表，支持多条件过滤"""
    items, total = await LocationService.get_list(
        page=page, page_size=page_size,
        location_code=location_code, location_name=location_name,
        parent_id=parent_id, warehouse_id=warehouse_id, warehouse_code=warehouse_code,
        location_type=location_type, usage=usage, is_active=is_active
    )
    items_dict = [await item.to_dict() for item in items]
    return success_response(data={"items": items_dict, "total": total, "page": page, "page_size": page_size})


@location_router.get("/tree", summary="获取库位树形结构")
async def get_location_tree(location_id: Optional[int] = Query(None, description="根库位ID（可选）")):
    """获取库位树形结构，用于层级展示"""
    tree = await LocationService.get_tree(location_id)
    return success_response(data=tree)


@location_router.get("/{location_id}/children", summary="获取子库位列表")
async def get_location_children(location_id: int):
    """获取指定库位的所有子库位"""
    children = await LocationService.get_children(location_id)
    children_dict = [await child.to_dict() for child in children]
    return success_response(data=children_dict)