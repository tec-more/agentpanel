from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

payment_router = APIRouter(prefix="/payments", tags=["付款管理"])


@payment_router.get("/", summary="获取付款单列表")
async def get_payments(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    supplier_id: Optional[int] = Query(None, description="供应商ID"),
    status: Optional[str] = Query(None, description="状态"),
    payment_date_start: Optional[str] = Query(None, description="付款日期开始"),
    payment_date_end: Optional[str] = Query(None, description="付款日期结束")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@payment_router.get("/{payment_id}", summary="获取付款单详情")
async def get_payment(payment_id: int):
    return SuccessResponse(data={"id": payment_id, "detail": {}})


@payment_router.post("/", summary="创建付款单")
async def create_payment():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@payment_router.post("/{payment_id}/confirm", summary="确认付款")
async def confirm_payment(payment_id: int):
    return SuccessResponse(msg="确认成功")


@payment_router.post("/{payment_id}/cancel", summary="取消付款")
async def cancel_payment(payment_id: int):
    return SuccessResponse(msg="取消成功")