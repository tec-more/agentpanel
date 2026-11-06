import uuid
import json
import asyncio
import logging
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone
from decimal import Decimal

from base.common.events.event_bus import EventBus
from base.common.events.connection_manager import RabbitMQConnectionManager
from base.common.setting import settings

logger = logging.getLogger(__name__)


class EventBusAdapter:
    def __init__(self):
        self._memory_bus = EventBus()
        self._connection_manager = RabbitMQConnectionManager()
        self._rabbitmq_available = False
        self._degraded_events: List[Dict] = []
        self._reconnect_task: Optional[asyncio.Task] = None
        self._degraded_since: Optional[datetime] = None
        self._handler_registry: Dict[str, List[Callable]] = {}
        self._connection_manager.set_status_change_callback(self._on_connection_status_change)

    def _on_connection_status_change(self, status: str):
        if status == "connected" and not self._rabbitmq_available:
            self._rabbitmq_available = True
            asyncio.ensure_future(self._recover_degraded_events())
        elif status == "disconnected" and self._rabbitmq_available:
            self._rabbitmq_available = False
            self._degraded_since = datetime.now(timezone.utc)
            self._connection_manager._check_cooldown()

    async def _recover_degraded_events(self):
        if not self._degraded_events:
            logger.info("RabbitMQ已恢复，无降级事件需补录")
            return
        try:
            from base.common.events.models.event_record import EventRecord
            count = 0
            for evt in self._degraded_events:
                try:
                    await EventRecord.filter(event_uuid=evt["event_uuid"]).update(status="degraded_consumed")
                    count += 1
                except Exception as e:
                    logger.warning(f"补录事件 {evt['event_uuid']} 失败: {e}")
            self._degraded_events.clear()
            self._degraded_since = None
            logger.info(f"RabbitMQ已恢复，补录 {count} 条降级事件")
        except Exception as e:
            logger.error(f"恢复降级事件失败: {e}")

    def _serialize_payload(self, kwargs: Dict[str, Any]) -> Dict:
        serialized = {}
        for k, v in kwargs.items():
            if isinstance(v, datetime):
                serialized[k] = v.isoformat()
            elif isinstance(v, Decimal):
                serialized[k] = float(v)
            elif isinstance(v, (str, int, float, bool, type(None))):
                serialized[k] = v
            elif isinstance(v, (list, dict)):
                serialized[k] = v
            else:
                serialized[k] = str(v)
        return serialized

    async def publish(self, event_name: str, **kwargs):
        event_uuid = str(uuid.uuid4())
        payload = self._serialize_payload(kwargs)
        now = datetime.now(timezone.utc)
        source_module = kwargs.pop("_source_module", None)

        try:
            from base.common.events.models.event_record import EventRecord
            if self._rabbitmq_available:
                try:
                    import aio_pika
                    body = json.dumps({"event_uuid": event_uuid, "event_name": event_name, "payload": payload, "published_at": now.isoformat()}, ensure_ascii=False).encode("utf-8")
                    message = aio_pika.Message(
                        body=body,
                        message_id=event_uuid,
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        content_type="application/json",
                        timestamp=now,
                    )
                    channel = self._connection_manager.get_channel()
                    exchange = self._connection_manager.get_exchange()
                    if channel and exchange:
                        await exchange.publish(message, routing_key=event_name)
                        await EventRecord.create(
                            event_uuid=event_uuid,
                            event_name=event_name,
                            payload=payload,
                            status="published",
                            published_at=now,
                            source_module=source_module,
                        )
                    else:
                        raise Exception("channel or exchange not available")
                except Exception as e:
                    logger.warning(f"RabbitMQ发布失败，降级为内存模式: {e}")
                    self._rabbitmq_available = False
                    self._degraded_since = datetime.now(timezone.utc)
                    await self._publish_degraded(event_uuid, event_name, payload, now, source_module, EventRecord)
            else:
                await self._publish_degraded(event_uuid, event_name, payload, now, source_module, EventRecord)
        except Exception as e:
            logger.error(f"事件记录写入失败: {e}")

        await self._memory_bus.publish(event_name, **kwargs)

    async def _publish_degraded(self, event_uuid, event_name, payload, now, source_module, EventRecord):
        try:
            await EventRecord.create(
                event_uuid=event_uuid,
                event_name=event_name,
                payload=payload,
                status="degraded_published",
                published_at=now,
                source_module=source_module,
            )
        except Exception as e:
            logger.error(f"降级事件记录写入失败: {e}")
        self._degraded_events.append({"event_uuid": event_uuid, "event_name": event_name})
        if not self._connection_manager._reconnect_task or self._connection_manager._reconnect_task.done():
            self._connection_manager._start_reconnect()

    def subscribe(self, event_name: str, handler: Callable):
        self._memory_bus.subscribe(event_name, handler)
        if event_name not in self._handler_registry:
            self._handler_registry[event_name] = []
        if handler not in self._handler_registry[event_name]:
            self._handler_registry[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Callable):
        self._memory_bus.unsubscribe(event_name, handler)
        if event_name in self._handler_registry and handler in self._handler_registry[event_name]:
            self._handler_registry[event_name].remove(handler)

    def get_handlers(self, event_name: str) -> List[Callable]:
        return self._handler_registry.get(event_name, [])

    def get_degradation_status(self) -> Dict[str, Any]:
        return {
            "is_degraded": not self._rabbitmq_available,
            "degraded_since": self._degraded_since.isoformat() if self._degraded_since else None,
            "pending_replay_count": len(self._degraded_events),
        }

    async def initialize(self):
        if not settings.RABBITMQ_ENABLED:
            logger.info("RabbitMQ未启用，使用纯内存事件总线")
            return
        connected = await self._connection_manager.connect()
        if connected:
            self._rabbitmq_available = True
            logger.info("EventBusAdapter初始化成功(RabbitMQ模式)")
        else:
            self._rabbitmq_available = False
            self._degraded_since = datetime.now(timezone.utc)
            logger.info("EventBusAdapter初始化成功(降级模式，RabbitMQ不可用)")

    async def shutdown(self):
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        await self._connection_manager.close()
        logger.info("EventBusAdapter已关闭")

    def get_connection_manager(self) -> RabbitMQConnectionManager:
        return self._connection_manager

    def is_rabbitmq_available(self) -> bool:
        return self._rabbitmq_available