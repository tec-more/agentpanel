from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

period_close_router = APIRouter(prefix="/period-close", tags=["期末结转"])


@period_close_router.get("/", summary="获取期间结转列表")
async def get_period_close(
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


@period_close_router.post("/", summary="执行期末结转")
async def close_period(
    period: str = Query(..., description="期间"),
    user_id: Optional[int] = Query(None, description="操作人")
):
    return SuccessResponse(msg="结转成功")


@period_close_router.post("/reverse", summary="反结账")
async def reverse_period(
    period: str = Query(..., description="期间"),
    user_id: Optional[int] = Query(None, description="操作人")
):
    return SuccessResponse(msg="反结账成功")