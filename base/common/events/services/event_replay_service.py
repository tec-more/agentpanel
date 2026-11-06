from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone

try:
    from base.common.events.models.event_record import EventRecord
    from base.common.events.models.replay_audit_log import ReplayAuditLog
    from base.common.events.services.event_record_service import EventRecordService
except ImportError:
    EventRecord = None
    ReplayAuditLog = None
    EventRecordService = None

from base.common.setting import settings
from loguru import logger


class EventReplayService:
    @staticmethod
    async def replay_event(event_uuid: str, operator: str, reason: str) -> Dict[str, Any]:
        if EventRecord is None:
            return {"success": False, "error": "EventRecord模型不可用"}

        record = await EventRecord.get_or_none(event_uuid=event_uuid)
        if not record:
            return {"success": False, "error": "EVENT_NOT_FOUND", "message": f"事件 {event_uuid} 不存在"}

        if record.status not in ("failed", "dead_letter"):
            return {"success": False, "error": "EVENT_STATUS_NOT_REPLAYABLE", "message": f"事件状态为 {record.status}，不可重放"}

        if not record.payload:
            return {"success": False, "error": "EVENT_PAYLOAD_CORRUPTED", "message": "事件载荷为空"}

        try:
            from base.common.events.event_bus import event_bus
            if hasattr(event_bus, 'is_rabbitmq_available') and not event_bus.is_rabbitmq_available():
                return {"success": False, "error": "RABBITMQ_UNAVAILABLE", "message": "RabbitMQ不可用"}

            await EventRecord.filter(event_uuid=event_uuid).update(
                status="published",
                retry_count=0,
                replay_count=record.replay_count + 1,
                error_message=None,
                published_at=datetime.now(timezone.utc),
            )

            payload = record.payload if isinstance(record.payload, dict) else {}
            await event_bus.publish(record.event_name, _source_module=record.source_module, **payload)

            await ReplayAuditLog.create(
                operator=operator,
                event_uuids=[event_uuid],
                reason=reason,
                result="success",
                success_count=1,
                fail_count=0,
            )

            return {"success": True, "event_uuid": event_uuid, "new_status": "published"}

        except Exception as e:
            logger.error(f"重放事件 {event_uuid} 失败: {e}")
            await ReplayAuditLog.create(
                operator=operator,
                event_uuids=[event_uuid],
                reason=reason,
                result="failed",
                success_count=0,
                fail_count=1,
                failed_event_uuids=[event_uuid],
            )
            return {"success": False, "error": str(e)}

    @staticmethod
    async def batch_replay(event_uuids: List[str], operator: str, reason: str) -> Dict[str, Any]:
        if EventRecordService is None:
            return {"success": False, "error": "服务不可用"}

        replayable = await EventRecordService.get_replayable_events(event_uuids)
        success_count = 0
        fail_count = 0
        failed_uuids = []

        for record in sorted(replayable, key=lambda r: r.published_at):
            result = await EventReplayService.replay_event(record.event_uuid, operator, reason)
            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1
                failed_uuids.append(record.event_uuid)

        overall_result = "success" if fail_count == 0 else ("partial" if success_count > 0 else "failed")

        if ReplayAuditLog is not None:
            await ReplayAuditLog.create(
                operator=operator,
                event_uuids=event_uuids,
                reason=reason,
                result=overall_result,
                success_count=success_count,
                fail_count=fail_count,
                failed_event_uuids=failed_uuids if failed_uuids else None,
            )

        return {
            "success": True,
            "result": overall_result,
            "success_count": success_count,
            "fail_count": fail_count,
            "failed_event_uuids": failed_uuids,
        }

    @staticmethod
    async def query_replay_audit_logs(operator: Optional[str] = None, start_date: Optional[str] = None,
                                       end_date: Optional[str] = None, page: int = 1, page_size: int = 20) -> Tuple[List, int]:
        if ReplayAuditLog is None:
            return [], 0
        query = ReplayAuditLog.all()
        if operator:
            query = query.filter(operator=operator)
        if start_date:
            query = query.filter(created_at__gte=start_date)
        if end_date:
            query = query.filter(created_at__lte=end_date)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.order_by("-created_at").offset(offset).limit(page_size)
        return items, total