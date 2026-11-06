from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from base.common.response import SuccessResponse

try:
    from base.plugins.finance.services.integration_log_service import IntegrationLogService
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

integration_log_router = APIRouter(prefix="/integration-logs", tags=["集成日志"])


@integration_log_router.get("/", summary="获取集成日志列表")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    event_name: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    total = await IntegrationLogService.get_log_count(event_name=event_name, source_type=source_type, result=result)
    items = await IntegrationLogService.get_all_logs(page=page, page_size=page_size, event_name=event_name, source_type=source_type, result=result)
    data = [await item.to_dict() for item in items]
    return SuccessResponse(data={"total": total, "page": page, "page_size": page_size, "data": data})


@integration_log_router.get("/failed", summary="获取失败日志列表")
async def get_failed_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    items = await IntegrationLogService.get_failed_logs(page=page, page_size=page_size)
    data = [await item.to_dict() for item in items]
    return SuccessResponse(data=data)


@integration_log_router.get("/{log_id}", summary="获取集成日志详情")
async def get_log(log_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    log = await IntegrationLogService.get_log_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")
    return SuccessResponse(data=await log.to_dict())


@integration_log_router.get("/source/{source_type}/{source_id}", summary="按来源查询日志")
async def get_logs_by_source(source_type: str, source_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    items = await IntegrationLogService.get_logs_by_source(source_type=source_type, source_id=source_id)
    data = [await item.to_dict() for item in items]
    return SuccessResponse(data=data)


@integration_log_router.post("/{log_id}/retry", summary="重试失败日志")
async def retry_failed_log(log_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    success = await IntegrationLogService.retry_failed_log(log_id)
    if not success:
        raise HTTPException(status_code=400, detail="无法重试该日志")
    return SuccessResponse(msg="已标记为重试")