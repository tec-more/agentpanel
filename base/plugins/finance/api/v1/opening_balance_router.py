from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

opening_balance_router = APIRouter(prefix="/opening-balance", tags=["期初余额"])


@opening_balance_router.get("/", summary="获取期初余额列表")
async def get_opening_balance(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    account_id: Optional[int] = Query(None, description="科目ID"),
    year: Optional[int] = Query(None, description="年份")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@opening_balance_router.post("/", summary="设置期初余额")
async def set_opening_balance(
    account_id: int = Query(..., description="科目ID"),
    year: int = Query(..., description="年份"),
    debit: float = Query(0, description="借方金额"),
    credit: float = Query(0, description="贷方金额")
):
    return SuccessResponse(msg="设置成功")


@opening_balance_router.post("/initialize", summary="初始化期初余额")
async def initialize_opening_balance(
    year: int = Query(..., description="年份")
):
    return SuccessResponse(msg="初始化成功")