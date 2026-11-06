from .event_record_router import event_record_router
from .event_replay_router import event_replay_router
from .event_monitor_router import event_monitor_router

from fastapi import APIRouter

events_api_router = APIRouter(prefix="/v1/events")

events_api_router.include_router(event_record_router)
events_api_router.include_router(event_replay_router)
events_api_router.include_router(event_monitor_router)

__all__ = ["events_api_router"]