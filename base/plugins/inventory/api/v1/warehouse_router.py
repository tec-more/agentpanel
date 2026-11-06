from typing import Optional
from fastapi import APIRouter, HTTPException, Query

try:
    from base.plugins.inventory.services.inventory_service import WarehouseService
    from base.plugins.inventory.schemas.inventory_schema import (
        StockWarehouseCreate, StockWarehouseUpdate, StockWarehouseResponse,
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

    class WarehouseService:
        @staticmethod
        async def get_by_id(id): return None
        @staticmethod
        async def create_warehouse(data): return None
        @staticmethod
        async def update_warehouse(id, data): return None
        @staticmethod
        async def delete_warehouse(id): return False
        @staticmethod
        async def get_list(**kwargs): return [], 0

    class StockWarehouseCreate: pass
    class StockWarehouseUpdate: pass
    class StockWarehouseResponse: pass
    class ListResponse: pass
    class MessageResponse: pass


warehouse_router = APIRouter(prefix="/warehouses", tags=["仓库管理"])


@warehouse_router.get("/{warehouse_id}", summary="获取仓库详情")
async def get_warehouse(warehouse_id: int):
    """根据ID获取仓库详情"""
    warehouse = await WarehouseService.get_by_id(warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="仓库不存在")
    return success_response(data=await warehouse.to_dict())


@warehouse_router.post("", summary="创建仓库")
async def create_warehouse(data: StockWarehouseCreate):
    """创建新仓库，可关联关键库位，验证关联库位有效性"""
    try:
        warehouse = await WarehouseService.create_warehouse(data)
        return success_response(data=await warehouse.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@warehouse_router.put("/{warehouse_id}", summary="更新仓库")
async def update_warehouse(warehouse_id: int, data: StockWarehouseUpdate):
    """更新仓库信息"""
    try:
        warehouse = await WarehouseService.update_warehouse(warehouse_id, data)
        if not warehouse:
            raise HTTPException(status_code=404, detail="仓库不存在")
        return success_response(data=await warehouse.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@warehouse_router.delete("/{warehouse_id}", summary="删除仓库")
async def delete_warehouse(warehouse_id: int):
    """删除仓库（需无关联库位）"""
    try:
        success = await WarehouseService.delete_warehouse(warehouse_id)
        if not success:
            raise HTTPException(status_code=404, detail="仓库不存在")
        return success_response(data={"message": "仓库删除成功"}, msg="仓库删除成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@warehouse_router.get("", summary="获取仓库列表")
async def list_warehouses(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    warehouse_code: Optional[str] = Query(None, description="仓库编码"),
    warehouse_name: Optional[str] = Query(None, description="仓库名称"),
    warehouse_type: Optional[str] = Query(None, description="仓库类型"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    """获取仓库列表，支持多条件过滤"""
    items, total = await WarehouseService.get_list(
        page=page, page_size=page_size,
        warehouse_code=warehouse_code, warehouse_name=warehouse_name,
        warehouse_type=warehouse_type, is_active=is_active
    )
    items_dict = [await item.to_dict() for item in items]
    return success_response(data={"items": items_dict, "total": total, "page": page, "page_size": page_size})