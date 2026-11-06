from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from base.common.response import SuccessResponse, fail_response

try:
    from base.common.events.services.event_replay_service import EventReplayService
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

event_replay_router = APIRouter(prefix="/replay", tags=["事件重放"])


class ReplayRequest(BaseModel):
    reason: str
    operator: str = "system"


class BatchReplayRequest(BaseModel):
    event_uuids: List[str]
    reason: str
    operator: str = "system"


@event_replay_router.post("/{event_uuid}", summary="单事件重放")
async def replay_event(event_uuid: str, req: ReplayRequest):
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    result = await EventReplayService.replay_event(event_uuid, req.operator, req.reason)
    if not result.get("success"):
        return fail_response(msg=result.get("message", result.get("error", "重放失败")), code=400)
    return SuccessResponse(data=result, msg="重放成功")


@event_replay_router.post("/batch", summary="批量事件重放")
async def batch_replay(req: BatchReplayRequest):
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    result = await EventReplayService.batch_replay(req.event_uuids, req.operator, req.reason)
    return SuccessResponse(data=result, msg="批量重放完成")


@event_replay_router.get("/audit-logs", summary="查询重放审计日志")
async def query_replay_audit_logs(
    operator: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    items, total = await EventReplayService.query_replay_audit_logs(
        operator=operator, start_date=start_date, end_date=end_date, page=page, page_size=page_size,
    )
    data = [await item.to_dict() for item in items]
    return SuccessResponse(data={"total": total, "page": page, "page_size": page_size, "data": data})