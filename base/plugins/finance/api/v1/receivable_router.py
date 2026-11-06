from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

receivable_router = APIRouter(prefix="/receivables", tags=["应收管理"])


@receivable_router.get("/", summary="获取应收单列表")
async def get_receivables(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    customer_id: Optional[int] = Query(None, description="客户ID"),
    status: Optional[str] = Query(None, description="状态"),
    due_date_start: Optional[str] = Query(None, description="到期日期开始"),
    due_date_end: Optional[str] = Query(None, description="到期日期结束"),
    keyword: Optional[str] = Query(None, description="搜索关键词")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@receivable_router.get("/{receivable_id}", summary="获取应收单详情")
async def get_receivable(receivable_id: int):
    return SuccessResponse(data={"id": receivable_id, "detail": {}})


@receivable_router.post("/", summary="创建应收单")
async def create_receivable():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@receivable_router.put("/{receivable_id}", summary="更新应收单")
async def update_receivable(receivable_id: int):
    return SuccessResponse(data={"id": receivable_id}, msg="更新成功")


@receivable_router.post("/{receivable_id}/confirm", summary="确认应收单")
async def confirm_receivable(receivable_id: int):
    return SuccessResponse(msg="确认成功")


@receivable_router.post("/{receivable_id}/cancel", summary="取消应收单")
async def cancel_receivable(receivable_id: int):
    return SuccessResponse(msg="取消成功")