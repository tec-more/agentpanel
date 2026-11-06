from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

expense_report_router = APIRouter(prefix="/expense-reports", tags=["报销单"])


@expense_report_router.get("/", summary="获取报销单列表")
async def get_expense_reports(
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


@expense_report_router.post("/", summary="创建报销单")
async def create_expense_report():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@expense_report_router.post("/{report_id}/reimburse", summary="执行报销")
async def reimburse_expense(report_id: int):
    return SuccessResponse(msg="报销成功")