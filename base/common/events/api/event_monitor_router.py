from fastapi import APIRouter, HTTPException

from base.common.response import SuccessResponse

try:
    from base.common.events.services.event_monitor_service import EventMonitorService
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

event_monitor_router = APIRouter(prefix="/monitor", tags=["事件监控"])


@event_monitor_router.get("/health", summary="事件系统健康检查")
async def get_health():
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    status = await EventMonitorService.get_health_status()
    return SuccessResponse(data=status)


@event_monitor_router.get("/connection", summary="查询RabbitMQ连接状态")
async def get_connection():
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    status = await EventMonitorService.get_connection_status()
    return SuccessResponse(data=status)


@event_monitor_router.get("/queues", summary="查询队列指标")
async def get_queue_metrics():
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    metrics = await EventMonitorService.get_queue_metrics()
    return SuccessResponse(data=metrics)


@event_monitor_router.get("/consumer", summary="查询消费者状态")
async def get_consumer_status():
    if not SERVICES_AVAILABLE:
        raise HTTPException(status_code=503, detail="事件服务不可用")
    status = await EventMonitorService.get_consumer_status()
    return SuccessResponse(data=status)