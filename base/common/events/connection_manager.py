import asyncio
import logging
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone

from base.common.setting import settings

logger = logging.getLogger(__name__)


class RabbitMQConnectionManager:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._exchange = None
        self._queue = None
        self._dlq_queue = None
        self._dlq_exchange = None
        self._status = "disconnected"
        self._connected_since: Optional[datetime] = None
        self._reconnect_count = 0
        self._disconnect_timestamps: List[datetime] = []
        self._is_in_cooldown = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._on_status_change: Optional[Callable] = None
        self._consuming_channel = None

    def set_status_change_callback(self, callback: Callable):
        self._on_status_change = callback

    async def connect(self) -> bool:
        if not settings.RABBITMQ_ENABLED:
            logger.info("RabbitMQ未启用，跳过连接")
            return False
        try:
            import aio_pika
        except ImportError:
            logger.warning("aio-pika未安装，RabbitMQ不可用")
            return False

        try:
            self._status = "connecting"
            self._notify_status_change()

            self._connection = await aio_pika.connect(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                virtualhost=settings.RABBITMQ_VIRTUAL_HOST,
                login=settings.RABBITMQ_USERNAME,
                password=settings.RABBITMQ_PASSWORD,
                heartbeat=settings.RABBITMQ_HEARTBEAT,
            )

            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)

            try:
                await self._channel.set_confirm(True)
            except AttributeError:
                pass

            self._dlq_exchange = await self._channel.declare_exchange(
                f"{settings.RABBITMQ_DLQ_NAME}.exchange",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            self._dlq_queue = await self._channel.declare_queue(
                settings.RABBITMQ_DLQ_NAME,
                durable=True,
            )
            await self._dlq_queue.bind(self._dlq_exchange, routing_key="#")

            self._exchange = await self._channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            queue_name = f"{settings.RABBITMQ_QUEUE_PREFIX}.main"
            self._queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": f"{settings.RABBITMQ_DLQ_NAME}.exchange",
                    "x-dead-letter-routing-key": "dead_letter",
                },
            )
            await self._queue.bind(self._exchange, routing_key="#")

            self._consuming_channel = await self._connection.channel()
            await self._consuming_channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)

            self._status = "connected"
            self._connected_since = datetime.now(timezone.utc)
            self._reconnect_count = 0
            self._is_in_cooldown = False
            self._notify_status_change()
            logger.info("RabbitMQ连接成功")
            return True

        except Exception as e:
            self._status = "disconnected"
            self._notify_status_change()
            logger.warning(f"RabbitMQ连接失败: {e}")
            self._start_reconnect()
            return False

    def _start_reconnect(self):
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.ensure_future(self._reconnect_loop())

    async def _reconnect_loop(self):
        interval = settings.RABBITMQ_CONNECTION_RETRY_INTERVAL
        max_retries = settings.RABBITMQ_MAX_RETRIES
        while self._status != "connected":
            if max_retries > 0 and self._reconnect_count >= max_retries:
                logger.warning(f"RabbitMQ重连已达最大次数({max_retries})，停止重连")
                return
            await asyncio.sleep(interval)
            if self._is_in_cooldown:
                continue
            try:
                if await self.connect():
                    return
            except Exception:
                pass
            self._reconnect_count += 1

    def _check_cooldown(self):
        now = datetime.now(timezone.utc)
        self._disconnect_timestamps.append(now)
        cutoff = now.timestamp() - 60
        recent = [t for t in self._disconnect_timestamps if t.timestamp() > cutoff]
        self._disconnect_timestamps = recent[-10:]
        if len(recent) >= 3:
            self._is_in_cooldown = True
            logger.warning(f"RabbitMQ抖动检测，进入冷却期({settings.RABBITMQ_DEGRADED_COOLDOWN}秒)")
            asyncio.ensure_future(self._exit_cooldown_after())

    async def _exit_cooldown_after(self):
        await asyncio.sleep(settings.RABBITMQ_DEGRADED_COOLDOWN)
        self._is_in_cooldown = False
        logger.info("RabbitMQ冷却期结束，恢复重连")

    def _notify_status_change(self):
        if self._on_status_change:
            try:
                self._on_status_change(self._status)
            except Exception:
                pass

    def is_connected(self) -> bool:
        if self._status != "connected" or self._connection is None:
            return False
        try:
            return not self._connection.is_closed
        except Exception:
            return False

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "status": self._status,
            "connected_since": self._connected_since.isoformat() if self._connected_since else None,
            "reconnect_count": self._reconnect_count,
            "is_in_cooldown": self._is_in_cooldown,
        }

    def get_channel(self):
        return self._channel

    def get_consuming_channel(self):
        return self._consuming_channel

    def get_exchange(self):
        return self._exchange

    def get_queue(self):
        return self._queue

    async def close(self):
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
        try:
            if self._connection:
                try:
                    if not self._connection.is_closed:
                        await self._connection.close()
                except Exception:
                    await self._connection.close()
        except Exception as e:
            logger.warning(f"关闭RabbitMQ连接时出错: {e}")
        self._status = "disconnected"
        self._connection = None
        self._channel = None
        self._exchange = None
        self._queue = None
        self._notify_status_change()