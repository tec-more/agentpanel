from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

expense_analysis_router = APIRouter(prefix="/expense-analysis", tags=["费用分析"])


@expense_analysis_router.get("/", summary="获取费用分析")
async def get_expense_analysis(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    department_id: Optional[int] = Query(None, description="部门ID"),
    period: Optional[str] = Query(None, description="期间")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })