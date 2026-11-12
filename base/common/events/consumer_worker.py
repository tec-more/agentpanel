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
        # 在途消息处理任务：关闭时须先排空，再关闭 channel / DB 连接（见 stop()）
        self._inflight: set[asyncio.Task] = set()

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
        """aio_pika 消息回调外壳：登记在途任务 + 关闭期异常隔离。

        aio_pika 为每条消息创建 Task 并挂 ``_task_done`` 回调，Task 一旦以异常
        结束，该回调会把异常抛到事件循环，产生成片 Traceback。关闭期尤其容易触发：
        DB 连接先关 -> ``asyncpg.pool.release`` 抛 CancelledError；channel 先关 ->
        ``message.process`` 的 ``__aexit__`` 访问 ``message.channel`` 抛
        ChannelInvalidStateError。此处统一收口，并由 :meth:`stop` 排空在途任务。
        """
        task = asyncio.current_task()
        if task is not None:
            self._inflight.add(task)
        try:
            await self._process_message(message)
        except asyncio.CancelledError:
            # 关闭期被取消属预期；吞掉以免 aio_pika 的 _task_done 把异常抛到事件循环
            logger.debug("消息处理在关闭期被取消，已忽略")
        except Exception as e:
            logger.error(f"消息处理异常(关闭期通道可能已失效): {e}")
        finally:
            if task is not None:
                self._inflight.discard(task)

    async def _process_message(self, message):
        """单条消息的业务处理（原 _on_message 主体，行为不变）。"""
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

    async def stop(self, drain_timeout: float = 8.0):
        """停止消费并**排空在途消息**后再返回。

        ``queue.cancel`` 只阻止新消息投递，已投递消息的 Task 仍在跑；若此时
        lifespan 继续关闭 RabbitMQ channel 或 DB 连接池，这些 Task 会抛
        CancelledError / ChannelInvalidStateError（历史事件处理 Traceback 的根因）。
        排空顺序必须是：cancel consumer -> 等在途 Task 收尾 -> 调用方再关闭
        event_bus / DB。超时后主动取消在途任务，避免关闭流程被无限拖住。
        """
        self._running = False
        try:
            queue = self._connection_manager.get_queue()
            if queue and self._consumer_tag:
                await queue.cancel(self._consumer_tag)
                self._consumer_tag = None
        except Exception as e:
            logger.warning(f"停止消费者时出错: {e}")

        loop = asyncio.get_running_loop()
        deadline = loop.time() + drain_timeout
        current = asyncio.current_task()
        while True:
            # 循环重取而非取一次快照：cancel 与 cancel-ok 之间可能仍有消息抵达
            pending = {t for t in self._inflight if t is not current and not t.done()}
            if not pending:
                break
            remaining = deadline - loop.time()
            if remaining <= 0:
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                logger.warning(f"关闭期 {len(pending)} 个消息处理任务超时，已主动取消")
                break
            await asyncio.wait(pending, timeout=min(remaining, 1.0))
        logger.info(f"ConsumerWorker已停止(在途任务已排空，剩余={len(self._inflight)})")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self._running,
            "prefetch_count": settings.RABBITMQ_PREFETCH_COUNT,
            "processed_count": self._processed_count,
        }