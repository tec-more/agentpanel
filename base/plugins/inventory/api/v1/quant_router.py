from typing import Optional
from fastapi import APIRouter, HTTPException, Query

try:
    from base.plugins.inventory.services.inventory_service import QuantService, ReservationService
    from base.plugins.inventory.schemas.inventory_schema import (
        StockQuantResponse, ListResponse, StockQuantSummary
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

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

    class Query:
        def __init__(self, default=None, **kwargs):
            self.default = default

    class QuantService:
        @staticmethod
        async def get_by_id(id): return None
        @staticmethod
        async def get_list(**kwargs): return [], 0
        @staticmethod
        async def get_summary(product_code=None): return {}
        @staticmethod
        async def get_by_product(product_code): return []
        @staticmethod
        async def get_by_location(location_id): return []

    class StockQuantResponse: pass
    class ListResponse: pass
    class StockQuantSummary: pass


quant_router = APIRouter(prefix="/quants", tags=["库存查询"])


@quant_router.get("", response_model=ListResponse, summary="获取库存列表")
async def list_quants(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    quant_code: Optional[str] = Query(None, description="库存编码"),
    product_code: Optional[str] = Query(None, description="产品编码"),
    location_id: Optional[int] = Query(None, description="库位ID"),
    location_code: Optional[str] = Query(None, description="库位编码"),
    lot_id: Optional[int] = Query(None, description="批次ID"),
    lot_name: Optional[str] = Query(None, description="批次号"),
    serial_no: Optional[str] = Query(None, description="序列号"),
    owner_id: Optional[int] = Query(None, description="所有者ID")
):
    """获取库存列表，支持多条件过滤"""
    items, total = await QuantService.get_list(
        page=page, page_size=page_size,
        quant_code=quant_code, product_code=product_code,
        location_id=location_id, location_code=location_code,
        lot_id=lot_id, lot_name=lot_name, serial_no=serial_no,
        owner_id=owner_id
    )
    items_dict = [await item.to_dict() for item in items]
    return success_response(data={"items": items_dict, "total": total, "page": page, "page_size": page_size})


@quant_router.get("/summary", summary="库存汇总统计")
async def get_quant_summary(product_code: Optional[str] = Query(None, description="产品编码（可选）")):
    """获取库存汇总统计"""
    summary = await QuantService.get_summary(product_code)
    return success_response(data=summary)


@quant_router.get("/by-product/{product_code}", summary="按产品查询库存")
async def get_quants_by_product(product_code: str):
    """按产品编码查询所有库存"""
    quants = await QuantService.get_by_product(product_code)
    quants_dict = [await quant.to_dict() for quant in quants]
    return success_response(data=quants_dict)


@quant_router.get("/by-location/{location_id}", summary="按库位查询库存")
async def get_quants_by_location(location_id: int):
    """按库位ID查询所有库存"""
    quants = await QuantService.get_by_location(location_id)
    quants_dict = [await quant.to_dict() for quant in quants]
    return success_response(data=quants_dict)


@quant_router.get("/reservations", summary="获取库存预留列表")
async def list_reservations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    product_code: Optional[str] = Query(None, description="产品编码"),
    location_name: Optional[str] = Query(None, description="库位名称")
):
    """获取库存预留列表，支持多条件过滤"""
    items, total = await ReservationService.get_list(
        page=page, page_size=page_size,
        product_code=product_code, location_name=location_name
    )
    items_dict = [await item.to_dict() for item in items]
    return success_response(data={"items": items_dict, "total": total, "page": page, "page_size": page_size})


@quant_router.get("/{quant_id}", summary="获取库存详情")
async def get_quant(quant_id: int):
    """根据ID获取库存详情"""
    quant = await QuantService.get_by_id(quant_id)
    if not quant:
        raise HTTPException(status_code=404, detail="库存不存在")
    return success_response(data=await quant.to_dict())