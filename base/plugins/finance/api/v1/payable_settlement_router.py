from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

payable_settlement_router = APIRouter(prefix="/payable-settlement", tags=["应付核销"])


@payable_settlement_router.get("/", summary="获取应付核销列表")
async def get_payable_settlement(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    supplier_id: Optional[int] = Query(None, description="供应商ID"),
    status: Optional[str] = Query(None, description="状态")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@payable_settlement_router.post("/", summary="执行应付核销")
async def settle_payable(
    payable_id: int = Query(..., description="应付单ID"),
    payment_id: int = Query(..., description="付款单ID"),
    amount: float = Query(..., description="核销金额")
):
    return SuccessResponse(msg="核销成功")