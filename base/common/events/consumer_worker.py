import json
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from base.common.events.connection_manager import RabbitMQConnectionManager
from base.common.setting import settings

logger = logging.getLogger(__name__)


class ConsumerWorker:
    def __init__(self, event_bus_adapter):
        self._adapter = event_bus_adapter
        self._running = False
        self._consumer_tag = None
        self._processed_count = 0
        self._connection_manager: RabbitMQConnectionManager = event_bus_adapter.get_connection_manager()

    async def start(self):
        if not settings.RABBITMQ_ENABLED:
            logger.info("RabbitMQ未启用，消费者不启动")
            return
        if not self._connection_manager.is_connected():
            logger.warning("RabbitMQ未连接，消费者不启动")
            return

        try:
            queue = self._connection_manager.get_queue()
            consuming_channel = self._connection_manager.get_consuming_channel()
            if not queue or not consuming_channel:
                logger.warning("RabbitMQ队列或消费通道不可用")
                return

            self._running = True
            self._consumer_tag = await queue.consume(self._on_message)
            logger.info("ConsumerWorker已启动")
        except Exception as e:
            logger.error(f"ConsumerWorker启动失败: {e}")
            self._running = False

    async def _on_message(self, message):
        async with message.process(requeue=False):
            try:
                body = json.loads(message.body.decode("utf-8"))
                event_uuid = body.get("event_uuid") or message.message_id
                event_name = body.get("event_name", "")
                payload = body.get("payload", {})
                published_at_str = body.get("published_at")

                if not event_uuid:
                    logger.warning("消息缺少event_uuid，跳过")
                    return

                from base.common.events.models.event_record import EventRecord

                await EventRecord.filter(event_uuid=event_uuid).update(status="consuming")

                handlers = self._adapter.get_handlers(event_name)
                if not handlers:
                    await EventRecord.filter(event_uuid=event_uuid).update(
                        status="consumed",
                        consumed_at=datetime.now(timezone.utc),
                    )
                    self._processed_count += 1
                    return

                start_time = datetime.now(timezone.utc)
                last_error = None
                for handler in handlers:
                    try:
                        result = handler(event_name, **payload)
                        if asyncio.iscoroutine(result):
                            await asyncio.wait_for(result, timeout=30)
                    except Exception as e:
                        last_error = str(e)
                        logger.error(f"事件处理器 {handler.__name__} 执行失败: {e}")

                if last_error:
                    record = await EventRecord.get_or_none(event_uuid=event_uuid)
                    if record:
                        new_retry = record.retry_count + 1
                        max_retries = settings.RABBITMQ_MAX_RETRIES
                        if new_retry >= max_retries:
                            await EventRecord.filter(event_uuid=event_uuid).update(
                                status="dead_letter",
                                retry_count=new_retry,
                                error_message=last_error,
                            )
                            logger.warning(f"事件 {event_uuid} 超过最大重试次数({max_retries})，进入死信队列")
                        else:
                            import random
                            delay = min(2 ** new_retry, 60)
                            from datetime import timedelta
                            next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
                            await EventRecord.filter(event_uuid=event_uuid).update(
                                status="failed",
                                retry_count=new_retry,
                                error_message=last_error,
                                next_retry_at=next_retry,
                            )
                            await message.nack(requeue=True)
                            return
                else:
                    processing_time = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    await EventRecord.filter(event_uuid=event_uuid).update(
                        status="consumed",
                        consumed_at=datetime.now(timezone.utc),
                        processing_time_ms=processing_time,
                    )

                self._processed_count += 1

            except json.JSONDecodeError as e:
                logger.error(f"消息JSON解析失败: {e}")
            except Exception as e:
                logger.error(f"消息处理异常: {e}", exc_info=True)

    async def stop(self):
        self._running = False
        try:
            queue = self._connection_manager.get_queue()
            if queue and self._consumer_tag:
                await queue.cancel(self._consumer_tag)
                self._consumer_tag = None
        except Exception as e:
            logger.warning(f"停止消费者时出错: {e}")
        logger.info("ConsumerWorker已停止")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self._running,
            "prefetch_count": settings.RABBITMQ_PREFETCH_COUNT,
            "processed_count": self._processed_count,
        }