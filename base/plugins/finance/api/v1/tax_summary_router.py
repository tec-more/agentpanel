from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

tax_summary_router = APIRouter(prefix="/tax-summary", tags=["税额汇总"])


@tax_summary_router.get("/", summary="获取税额汇总")
async def get_tax_summary(
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