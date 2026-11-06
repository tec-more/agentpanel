from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

aging_analysis_router = APIRouter(prefix="/aging-analysis", tags=["账龄分析"])


@aging_analysis_router.get("/", summary="获取账龄分析")
async def get_aging_analysis(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    type: str = Query("receivable", description="类型(receivable/payable)"),
    party_id: Optional[int] = Query(None, description="客户/供应商ID"),
    as_of_date: Optional[str] = Query(None, description="截止日期")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })