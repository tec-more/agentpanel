from typing import Optional
from fastapi import APIRouter, HTTPException

from base.plugins.mrp2.services.mrp_service import MonitorService, AlertService
from base.plugins.mrp2.schemas.mrp_schema import (
    MonitorCreate,
    AlertCreate
)
from base.common.response import success_response

monitor_router = APIRouter(prefix="/monitor", tags=["计划执行监控"])

@monitor_router.get("", summary="获取监控列表")
async def list_monitors(
    page: int = 1,
    page_size: int = 10,
    monitor_code: Optional[str] = None,
    monitor_name: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await MonitorService.get_list(
        page=page, page_size=page_size,
        monitor_code=monitor_code,
        monitor_name=monitor_name,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@monitor_router.post("", summary="创建监控")
async def create_monitor(data: MonitorCreate):
    try:
        monitor = await MonitorService.create_monitor(data)
        return success_response(data=monitor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@monitor_router.get("/alerts", summary="获取告警列表")
async def list_alerts(
    page: int = 1,
    page_size: int = 10,
    alert_code: Optional[str] = None,
    alert_type: Optional[str] = None,
    alert_level: Optional[str] = None,
    alert_status: Optional[str] = None
):
    items, total = await AlertService.get_list(
        page=page, page_size=page_size,
        alert_code=alert_code,
        alert_type=alert_type,
        alert_level=alert_level,
        alert_status=alert_status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@monitor_router.get("/alerts/{alert_id}", summary="获取告警详情")
async def get_alert(alert_id: int):
    alert = await AlertService.get_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    return success_response(data=alert)

@monitor_router.post("/alerts", summary="创建告警")
async def create_alert(data: AlertCreate):
    try:
        alert = await AlertService.create_alert(data)
        return success_response(data=alert)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@monitor_router.put("/alerts/{alert_id}", summary="更新告警")
async def update_alert(alert_id: int, data: dict):
    alert = await AlertService.update_alert(alert_id, data)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    return success_response(data=alert)

@monitor_router.delete("/alerts/{alert_id}", summary="删除告警")
async def delete_alert(alert_id: int):
    success = await AlertService.delete_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="告警不存在")
    return success_response(data={"message": "告警删除成功"}, msg="告警删除成功")

@monitor_router.put("/alerts/{alert_id}/resolve", summary="处理告警")
async def resolve_alert(alert_id: int, data: dict):
    resolved_by = data.get('resolved_by', '')
    resolved_note = data.get('resolved_note', '')
    try:
        alert = await AlertService.resolve_alert(alert_id, resolved_by, resolved_note)
        if not alert:
            raise HTTPException(status_code=404, detail="告警不存在")
        return success_response(data=alert)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@monitor_router.get("/alerts/active", summary="获取活跃告警")
async def get_active_alerts(monitor_id: Optional[int] = None):
    alerts = await AlertService.get_active_alerts(monitor_id)
    return success_response(data=alerts)

@monitor_router.get("/stats", summary="获取监控统计")
async def get_monitor_stats():
    stats = await MonitorService.get_stats()
    return success_response(data=stats)

@monitor_router.get("/{monitor_id}", summary="获取监控详情")
async def get_monitor(monitor_id: int):
    monitor = await MonitorService.get_by_id(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控不存在")
    return success_response(data=monitor)

@monitor_router.put("/{monitor_id}", summary="更新监控")
async def update_monitor(monitor_id: int, data: dict):
    monitor = await MonitorService.update_monitor(monitor_id, data)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控不存在")
    return success_response(data=monitor)

@monitor_router.delete("/{monitor_id}", summary="删除监控")
async def delete_monitor(monitor_id: int):
    success = await MonitorService.delete_monitor(monitor_id)
    if not success:
        raise HTTPException(status_code=404, detail="监控不存在")
    return success_response(data={"message": "监控删除成功"}, msg="监控删除成功")

@monitor_router.put("/{monitor_id}/metrics", summary="更新监控指标")
async def update_monitor_metrics(monitor_id: int):
    monitor = await MonitorService.update_metrics(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控不存在")
    return success_response(data=monitor)

@monitor_router.get("/{monitor_id}/alerts", summary="获取监控告警列表")
async def get_monitor_alerts(monitor_id: int):
    alerts = await AlertService.get_active_alerts(monitor_id)
    return success_response(data=alerts)

@monitor_router.put("/{monitor_id}/pause", summary="暂停监控")
async def pause_monitor(monitor_id: int):
    monitor = await MonitorService.pause_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控不存在")
    return success_response(data=monitor)

@monitor_router.put("/{monitor_id}/resume", summary="恢复监控")
async def resume_monitor(monitor_id: int):
    monitor = await MonitorService.resume_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="监控不存在")
    return success_response(data=monitor)