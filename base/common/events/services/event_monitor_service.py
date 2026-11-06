from typing import Dict, Any

from base.common.setting import settings


class EventMonitorService:
    @staticmethod
    async def get_health_status() -> Dict[str, Any]:
        from base.common.events.event_bus import event_bus
        result = {
            "rabbitmq_connection_status": "unknown",
            "main_queue_depth": -1,
            "dlq_depth": -1,
            "consumer_status": {},
            "degradation_status": {},
        }

        if not settings.RABBITMQ_ENABLED:
            result["rabbitmq_connection_status"] = "disabled"
            return result

        if hasattr(event_bus, 'get_connection_manager'):
            cm = event_bus.get_connection_manager()
            result["rabbitmq_connection_status"] = cm.get_connection_status().get("status", "unknown")

            try:
                queue = cm.get_queue()
                if queue:
                    queue_info = await queue.declare(passive=True)
                    result["main_queue_depth"] = queue_info.message_count
            except Exception:
                result["main_queue_depth"] = -1

            try:
                dlq = cm._dlq_queue
                if dlq:
                    dlq_info = await dlq.declare(passive=True)
                    result["dlq_depth"] = dlq_info.message_count
            except Exception:
                result["dlq_depth"] = -1

        if hasattr(event_bus, '_consumer_worker') and event_bus._consumer_worker:
            result["consumer_status"] = event_bus._consumer_worker.get_status()

        if hasattr(event_bus, 'get_degradation_status'):
            result["degradation_status"] = event_bus.get_degradation_status()

        return result

    @staticmethod
    async def get_connection_status() -> Dict[str, Any]:
        from base.common.events.event_bus import event_bus
        if not settings.RABBITMQ_ENABLED:
            return {"status": "disabled"}
        if hasattr(event_bus, 'get_connection_manager'):
            return event_bus.get_connection_manager().get_connection_status()
        return {"status": "unknown"}

    @staticmethod
    async def get_queue_metrics() -> Dict[str, Any]:
        result = {"main_queue": {"message_count": -1, "consumer_count": 0}, "dlq": {"message_count": -1}}
        if not settings.RABBITMQ_ENABLED:
            return result

        from base.common.events.event_bus import event_bus
        if hasattr(event_bus, 'get_connection_manager'):
            cm = event_bus.get_connection_manager()
            try:
                queue = cm.get_queue()
                if queue:
                    info = await queue.declare(passive=True)
                    result["main_queue"] = {"message_count": info.message_count, "consumer_count": info.consumer_count}
            except Exception:
                pass
            try:
                dlq = cm._dlq_queue
                if dlq:
                    dlq_info = await dlq.declare(passive=True)
                    result["dlq"] = {"message_count": dlq_info.message_count}
            except Exception:
                pass

        return result

    @staticmethod
    async def get_consumer_status() -> Dict[str, Any]:
        from base.common.events.event_bus import event_bus
        if hasattr(event_bus, '_consumer_worker') and event_bus._consumer_worker:
            return event_bus._consumer_worker.get_status()
        return {"is_running": False, "prefetch_count": 0, "processed_count": 0}