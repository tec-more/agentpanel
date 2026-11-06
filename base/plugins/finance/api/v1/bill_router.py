from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

bill_router = APIRouter(prefix="/bills", tags=["票据管理"])


@bill_router.get("/", summary="获取票据列表")
async def get_bills(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    bill_type: Optional[str] = Query(None, description="票据类型"),
    status: Optional[str] = Query(None, description="状态"),
    maturity_date: Optional[str] = Query(None, description="到期日期")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@bill_router.get("/{bill_id}", summary="获取票据详情")
async def get_bill(bill_id: int):
    return SuccessResponse(data={"id": bill_id, "detail": {}})


@bill_router.post("/", summary="创建票据")
async def create_bill():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@bill_router.post("/{bill_id}/endorse", summary="背书票据")
async def endorse_bill(bill_id: int):
    return SuccessResponse(msg="背书成功")


@bill_router.post("/{bill_id}/discount", summary="贴现票据")
async def discount_bill(bill_id: int):
    return SuccessResponse(msg="贴现成功")


@bill_router.post("/{bill_id}/void", summary="作废票据")
async def void_bill(bill_id: int):
    return SuccessResponse(msg="作废成功")