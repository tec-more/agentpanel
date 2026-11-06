from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from base.plugins.mes.services.production_report_service import ProductionReportService
from base.plugins.mes.schemas.production_report_schema import (
    ProductionReportCreate, BatchReportRequest, ProductionReportListQuery
)
from base.common.response import success_response
from base.common.security import get_current_user_id

production_report_router = APIRouter(prefix="/production-report", tags=["生产报工"])

@production_report_router.post("", summary="提交生产报工")
async def submit_report(data: ProductionReportCreate, user_id: str = Depends(get_current_user_id)):
    try:
        report = await ProductionReportService.submit_report(data, operator=user_id)
        return success_response(data=report, msg="报工成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_report_router.post("/batch", summary="批量报工")
async def batch_report(data: BatchReportRequest, user_id: str = Depends(get_current_user_id)):
    try:
        result = await ProductionReportService.batch_report(data, operator=user_id)
        return success_response(data=result, msg=f"批量报工完成，成功{result['success_count']}条，失败{result['fail_count']}条")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_report_router.get("", summary="查询报工记录")
async def list_reports(
    page: int = 1,
    page_size: int = 10,
    wo_code: Optional[str] = None,
    mo_code: Optional[str] = None,
    operator: Optional[str] = None,
    batch_no: Optional[str] = None,
    work_center_code: Optional[str] = None
):
    items, total = await ProductionReportService.get_list(
        page=page, page_size=page_size,
        wo_code=wo_code, mo_code=mo_code,
        operator=operator, batch_no=batch_no,
        work_center_code=work_center_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})