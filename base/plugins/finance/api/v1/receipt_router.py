from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

receipt_router = APIRouter(prefix="/receipts", tags=["收款管理"])


@receipt_router.get("/", summary="获取收款单列表")
async def get_receipts(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    status: Optional[str] = Query(None, description="状态"),
    receipt_date_start: Optional[str] = Query(None, description="收款日期开始"),
    receipt_date_end: Optional[str] = Query(None, description="收款日期结束")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@receipt_router.get("/{receipt_id}", summary="获取收款单详情")
async def get_receipt(receipt_id: int):
    return SuccessResponse(data={"id": receipt_id, "detail": {}})


@receipt_router.post("/", summary="创建收款单")
async def create_receipt():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@receipt_router.post("/{receipt_id}/confirm", summary="确认收款")
async def confirm_receipt(receipt_id: int):
    return SuccessResponse(msg="确认成功")


@receipt_router.post("/{receipt_id}/cancel", summary="取消收款")
async def cancel_receipt(receipt_id: int):
    return SuccessResponse(msg="取消成功")