from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

receivable_settlement_router = APIRouter(prefix="/receivable-settlement", tags=["应收核销"])


@receivable_settlement_router.get("/", summary="获取应收核销列表")
async def get_receivable_settlement(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    status: Optional[str] = Query(None, description="状态")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@receivable_settlement_router.post("/", summary="执行应收核销")
async def settle_receivable(
    receivable_id: int = Query(..., description="应收单ID"),
    receipt_id: int = Query(..., description="收款单ID"),
    amount: float = Query(..., description="核销金额")
):
    return SuccessResponse(msg="核销成功")