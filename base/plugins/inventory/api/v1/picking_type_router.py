from typing import Optional
from fastapi import APIRouter, HTTPException, Query

try:
    from base.plugins.inventory.services.inventory_service import PickingTypeService
    from base.plugins.inventory.schemas.inventory_schema import (
        StockPickingTypeCreate, StockPickingTypeUpdate, StockPickingTypeResponse,
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

    class PickingTypeService:
        @staticmethod
        async def get_by_id(id): return None
        @staticmethod
        async def create_picking_type(data): return None
        @staticmethod
        async def update_picking_type(id, data): return None
        @staticmethod
        async def delete_picking_type(id): return False
        @staticmethod
        async def get_list(**kwargs): return [], 0

    class StockPickingTypeCreate: pass
    class StockPickingTypeUpdate: pass
    class StockPickingTypeResponse: pass
    class ListResponse: pass
    class MessageResponse: pass


picking_type_router = APIRouter(prefix="/picking-types", tags=["调拨类型管理"])


@picking_type_router.get("/{picking_type_id}", summary="获取调拨类型详情")
async def get_picking_type(picking_type_id: int):
    """根据ID获取调拨类型详情"""
    picking_type = await PickingTypeService.get_by_id(picking_type_id)
    if not picking_type:
        raise HTTPException(status_code=404, detail="调拨类型不存在")
    return success_response(data=await picking_type.to_dict())


@picking_type_router.post("", summary="创建调拨类型")
async def create_picking_type(data: StockPickingTypeCreate):
    """创建新调拨类型，定义序列码模板"""
    try:
        picking_type = await PickingTypeService.create_picking_type(data)
        return success_response(data=await picking_type.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@picking_type_router.put("/{picking_type_id}", summary="更新调拨类型")
async def update_picking_type(picking_type_id: int, data: StockPickingTypeUpdate):
    """更新调拨类型信息"""
    try:
        picking_type = await PickingTypeService.update_picking_type(picking_type_id, data)
        if not picking_type:
            raise HTTPException(status_code=404, detail="调拨类型不存在")
        return success_response(data=await picking_type.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@picking_type_router.delete("/{picking_type_id}", summary="删除调拨类型")
async def delete_picking_type(picking_type_id: int):
    """删除调拨类型（需无调拨单）"""
    try:
        success = await PickingTypeService.delete_picking_type(picking_type_id)
        if not success:
            raise HTTPException(status_code=404, detail="调拨类型不存在")
        return success_response(data={"message": "调拨类型删除成功"}, msg="调拨类型删除成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@picking_type_router.get("", summary="获取调拨类型列表")
async def list_picking_types(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    picking_type_code: Optional[str] = Query(None, description="调拨类型编码"),
    picking_type_name: Optional[str] = Query(None, description="调拨类型名称"),
    code: Optional[str] = Query(None, description="类型代码"),
    warehouse_id: Optional[int] = Query(None, description="仓库ID"),
    warehouse_code: Optional[str] = Query(None, description="仓库编码"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    """获取调拨类型列表，支持多条件过滤"""
    items, total = await PickingTypeService.get_list(
        page=page, page_size=page_size,
        picking_type_code=picking_type_code, picking_type_name=picking_type_name,
        code=code, warehouse_id=warehouse_id, warehouse_code=warehouse_code,
        is_active=is_active
    )
    items_dict = [await item.to_dict() for item in items]
    return success_response(data={"items": items_dict, "total": total, "page": page, "page_size": page_size})