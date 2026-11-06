from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

depreciation_router = APIRouter(prefix="/depreciation", tags=["折旧计提"])


@depreciation_router.get("/", summary="获取折旧记录")
async def get_depreciation(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    period: Optional[str] = Query(None, description="期间"),
    asset_id: Optional[int] = Query(None, description="资产ID")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@depreciation_router.post("/", summary="执行折旧计提")
async def execute_depreciation(
    period: str = Query(..., description="期间")
):
    return SuccessResponse(msg="折旧计提成功")