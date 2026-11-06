from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

cash_flow_router = APIRouter(prefix="/cash-flow", tags=["资金流水"])


@cash_flow_router.get("/", summary="获取资金流水列表")
async def get_cash_flow(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    account_id: Optional[int] = Query(None, description="账户ID"),
    type: Optional[str] = Query(None, description="类型(income/expense)"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })