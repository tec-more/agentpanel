from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

inventory_cost_router = APIRouter(prefix="/inventory-cost", tags=["存货成本"])


@inventory_cost_router.get("/", summary="获取存货成本列表")
async def get_inventory_cost(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    product_id: Optional[int] = Query(None, description="产品ID"),
    cost_method: Optional[str] = Query(None, description="计价方法")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


cost_transfer_router = APIRouter(prefix="/cost-transfer", tags=["成本结转"])


@cost_transfer_router.get("/", summary="获取成本结转列表")
async def get_cost_transfer(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    period: Optional[str] = Query(None, description="期间")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@cost_transfer_router.post("/", summary="执行成本结转")
async def execute_cost_transfer(
    period: str = Query(..., description="期间")
):
    return SuccessResponse(msg="成本结转成功")


cost_variance_router = APIRouter(prefix="/cost-variance", tags=["成本差异"])


@cost_variance_router.get("/", summary="获取成本差异列表")
async def get_cost_variance(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    product_id: Optional[int] = Query(None, description="产品ID"),
    period: Optional[str] = Query(None, description="期间")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


__all__ = ["inventory_cost_router", "cost_transfer_router", "cost_variance_router"]