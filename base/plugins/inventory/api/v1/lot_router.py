from typing import Optional
from fastapi import APIRouter, HTTPException, Query

try:
    from base.plugins.inventory.services.inventory_service import LotService
    from base.plugins.inventory.schemas.inventory_schema import (
        StockLotCreate, StockLotUpdate, StockLotResponse,
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

    class LotService:
        @staticmethod
        async def get_by_id(id): return None
        @staticmethod
        async def create_lot(data): return None
        @staticmethod
        async def update_lot(id, data): return None
        @staticmethod
        async def delete_lot(id): return False
        @staticmethod
        async def get_list(**kwargs): return [], 0

    class StockLotCreate: pass
    class StockLotUpdate: pass
    class StockLotResponse: pass
    class ListResponse: pass
    class MessageResponse: pass


lot_router = APIRouter(prefix="/lots", tags=["批次管理"])


@lot_router.get("/{lot_id}", summary="获取批次详情")
async def get_lot(lot_id: int):
    """根据ID获取批次详情"""
    lot = await LotService.get_by_id(lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="批次不存在")
    return success_response(data=await lot.to_dict())


@lot_router.post("", summary="创建批次")
async def create_lot(data: StockLotCreate):
    """创建新批次"""
    try:
        lot = await LotService.create_lot(data)
        return success_response(data=await lot.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@lot_router.put("/{lot_id}", summary="更新批次")
async def update_lot(lot_id: int, data: StockLotUpdate):
    """更新批次信息"""
    try:
        lot = await LotService.update_lot(lot_id, data)
        if not lot:
            raise HTTPException(status_code=404, detail="批次不存在")
        return success_response(data=await lot.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@lot_router.delete("/{lot_id}", summary="删除批次")
async def delete_lot(lot_id: int):
    """删除批次（需无库存）"""
    try:
        success = await LotService.delete_lot(lot_id)
        if not success:
            raise HTTPException(status_code=404, detail="批次不存在")
        return success_response(data={"message": "批次删除成功"}, msg="批次删除成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@lot_router.get("", summary="获取批次列表")
async def list_lots(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    lot_code: Optional[str] = Query(None, description="批次编码"),
    lot_name: Optional[str] = Query(None, description="批次名称"),
    product_code: Optional[str] = Query(None, description="产品编码"),
    is_active: Optional[bool] = Query(None, description="是否启用")
):
    """获取批次列表，支持多条件过滤"""
    items, total = await LotService.get_list(
        page=page, page_size=page_size,
        lot_code=lot_code, lot_name=lot_name,
        product_code=product_code, is_active=is_active
    )
    items_dict = [await item.to_dict() for item in items]
    return success_response(data={"items": items_dict, "total": total, "page": page, "page_size": page_size})