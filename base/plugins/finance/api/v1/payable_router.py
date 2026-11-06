from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

payable_router = APIRouter(prefix="/payables", tags=["应付管理"])


@payable_router.get("/", summary="获取应付单列表")
async def get_payables(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    supplier_id: Optional[int] = Query(None, description="供应商ID"),
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


@payable_router.get("/{payable_id}", summary="获取应付单详情")
async def get_payable(payable_id: int):
    return SuccessResponse(data={"id": payable_id, "detail": {}})


@payable_router.post("/", summary="创建应付单")
async def create_payable():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@payable_router.put("/{payable_id}", summary="更新应付单")
async def update_payable(payable_id: int):
    return SuccessResponse(data={"id": payable_id}, msg="更新成功")


@payable_router.post("/{payable_id}/confirm", summary="确认应付单")
async def confirm_payable(payable_id: int):
    return SuccessResponse(msg="确认成功")


@payable_router.post("/{payable_id}/cancel", summary="取消应付单")
async def cancel_payable(payable_id: int):
    return SuccessResponse(msg="取消成功")