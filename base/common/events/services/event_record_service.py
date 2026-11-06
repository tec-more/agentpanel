from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

try:
    from base.common.events.models.event_record import EventRecord
except ImportError:
    EventRecord = None


class EventRecordService:
    @staticmethod
    async def create_event_record(event_uuid: str, event_name: str, payload: Dict, status: str, source_module: Optional[str] = None) -> Optional[EventRecord]:
        if EventRecord is None:
            return None
        return await EventRecord.create(
            event_uuid=event_uuid,
            event_name=event_name,
            payload=payload,
            status=status,
            published_at=datetime.utcnow(),
            source_module=source_module,
        )

    @staticmethod
    async def update_event_status(event_uuid: str, status: str, **kwargs) -> bool:
        if EventRecord is None:
            return False
        update_fields = {"status": status}
        for field in ["retry_count", "error_message", "consumed_at", "processing_time_ms", "next_retry_at", "replay_count"]:
            if field in kwargs:
                update_fields[field] = kwargs[field]
        result = await EventRecord.filter(event_uuid=event_uuid).update(**update_fields)
        return result > 0

    @staticmethod
    async def get_event_by_uuid(event_uuid: str) -> Optional[EventRecord]:
        if EventRecord is None:
            return None
        return await EventRecord.get_or_none(event_uuid=event_uuid)

    @staticmethod
    async def query_events(event_name: Optional[str] = None, status: Optional[str] = None,
                           source_module: Optional[str] = None, start_date: Optional[str] = None,
                           end_date: Optional[str] = None, page: int = 1, page_size: int = 20) -> Tuple[List[EventRecord], int]:
        if EventRecord is None:
            return [], 0
        query = EventRecord.all()
        if event_name:
            query = query.filter(event_name=event_name)
        if status:
            query = query.filter(status=status)
        if source_module:
            query = query.filter(source_module=source_module)
        if start_date:
            query = query.filter(published_at__gte=start_date)
        if end_date:
            query = query.filter(published_at__lte=end_date)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.order_by("-published_at").offset(offset).limit(page_size)
        return items, total

    @staticmethod
    async def get_event_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None, group_by: Optional[str] = None) -> Dict:
        if EventRecord is None:
            return {}
        query = EventRecord.all()
        if start_date:
            query = query.filter(published_at__gte=start_date)
        if end_date:
            query = query.filter(published_at__lte=end_date)
        records = await query
        if group_by == "event_name":
            stats = {}
            for r in records:
                stats[r.event_name] = stats.get(r.event_name, 0) + 1
            return stats
        elif group_by == "status":
            stats = {}
            for r in records:
                stats[r.status] = stats.get(r.status, 0) + 1
            return stats
        elif group_by == "source_module":
            stats = {}
            for r in records:
                key = r.source_module or "unknown"
                stats[key] = stats.get(key, 0) + 1
            return stats
        return {"total": len(records)}

    @staticmethod
    async def get_replayable_events(event_uuids: List[str]) -> List[EventRecord]:
        if EventRecord is None:
            return []
        return await EventRecord.filter(event_uuid__in=event_uuids, status__in=["failed", "dead_letter"])