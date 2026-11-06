from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse, fail_response

try:
    from base.common.events.services.event_record_service import EventRecordService
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

event_record_router = APIRouter(prefix="/records", tags=["事件追踪"])


@event_record_router.get("/", summary="查询事件记录列表")
async def query_events(
    event_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source_module: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    items, total = await EventRecordService.query_events(
        event_name=event_name, status=status, source_module=source_module,
        start_date=start_date, end_date=end_date, page=page, page_size=page_size,
    )
    data = [await item.to_dict() for item in items]
    return SuccessResponse(data={"total": total, "page": page, "page_size": page_size, "data": data})


@event_record_router.get("/statistics", summary="事件统计")
async def get_statistics(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    group_by: Optional[str] = Query(None, description="分组字段: event_name/status/source_module"),
):
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    stats = await EventRecordService.get_event_statistics(start_date=start_date, end_date=end_date, group_by=group_by)
    return SuccessResponse(data=stats)


@event_record_router.get("/{event_uuid}", summary="查询事件记录详情")
async def get_event_detail(event_uuid: str):
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    record = await EventRecordService.get_event_by_uuid(event_uuid)
    if not record:
        return fail_response(msg="事件不存在", code=404)
    return SuccessResponse(data=await record.to_dict())