from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

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
