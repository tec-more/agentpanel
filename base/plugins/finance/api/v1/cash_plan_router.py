from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

cash_plan_router = APIRouter(prefix="/cash-plan", tags=["资金计划"])


@cash_plan_router.get("/", summary="获取资金计划列表")
async def get_cash_plan(
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


@cash_plan_router.post("/", summary="创建资金计划")
async def create_cash_plan():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@cash_plan_router.put("/{plan_id}", summary="更新资金计划")
async def update_cash_plan(plan_id: int):
    return SuccessResponse(data={"id": plan_id}, msg="更新成功")