from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

expense_router = APIRouter(prefix="/expense-applies", tags=["费用管理"])


@expense_router.get("/", summary="获取费用申请列表")
async def get_expenses(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    applicant_id: Optional[int] = Query(None, description="申请人ID"),
    status: Optional[str] = Query(None, description="状态"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@expense_router.get("/{expense_id}", summary="获取费用申请详情")
async def get_expense(expense_id: int):
    return SuccessResponse(data={"id": expense_id, "detail": {}})


@expense_router.post("/", summary="创建费用申请")
async def create_expense():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@expense_router.post("/{expense_id}/approve", summary="审批费用申请")
async def approve_expense(expense_id: int):
    return SuccessResponse(msg="审批通过")


@expense_router.post("/{expense_id}/reject", summary="拒绝费用申请")
async def reject_expense(expense_id: int):
    return SuccessResponse(msg="已拒绝")