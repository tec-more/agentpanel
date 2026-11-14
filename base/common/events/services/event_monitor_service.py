"""事件链路监控（M3 后：探针基于 taskiq broker 与 Redis 心跳键）。

旧的 RabbitMQConnectionManager 队列深度探针与 ConsumerWorker 状态已随消费外迁
删除；等价观测改为：
- broker 客户端连接态（app 进程 publish 所需的 taskiq 客户端连接）；
- taskiq worker / beat 的 Redis 心跳键年龄（health.py healthcheck 同源）。
队列深度等 MQ 侧指标可经 RabbitMQ 管理接口获取，不再在应用内被动探测。
"""
from typing import Dict, Any

from base.common.setting import settings

_HEARTBEAT_MAX_AGE = 30.0  # 心跳键 ex=30s，超过即视为进程不在


async def _heartbeat_age(key: str) -> float:
    """读取 Redis 心跳键的时间戳，返回距今秒数；键缺失返回 -1。"""
    try:
        from base.common.cache import RedisCache

        rc = await RedisCache.get_instance()
        raw = await rc.get(key)
        if not raw:
            return -1.0
        # RedisCache set/get 走 JSON 序列化：写入 str 会被读回为 str
        ts = float(raw if isinstance(raw, (int, float, str)) else 0)
        import time

        return max(time.time() - ts, 0.0)
    except Exception:
        return -1.0


def _broker_client_status() -> str:
    try:
        from base.common.taskiq_app import broker as broker_mod

        return "connected" if broker_mod._startup_done else "disconnected"
    except Exception:
        return "unknown"


class EventMonitorService:
    @staticmethod
    async def get_health_status() -> Dict[str, Any]:
        worker_age = await _heartbeat_age("ap:taskiq:worker:heartbeat")
        beat_age = await _heartbeat_age("ap:taskiq:beat:heartbeat")
        return {
            "broker_client_status": _broker_client_status(),
            "taskiq_worker": {
                "alive": 0 <= worker_age <= _HEARTBEAT_MAX_AGE,
                "heartbeat_age_s": worker_age,
            },
            "taskiq_beat": {
                "alive": 0 <= beat_age <= _HEARTBEAT_MAX_AGE,
                "heartbeat_age_s": beat_age,
            },
        }

    @staticmethod
    async def get_connection_status() -> Dict[str, Any]:
        if not settings.RABBITMQ_ENABLED:
            return {"status": "disabled"}
        return {"status": _broker_client_status()}

    @staticmethod
    async def get_queue_metrics() -> Dict[str, Any]:
        # 队列深度属 MQ 侧指标：改由 RabbitMQ 管理接口 / beat run 历史观测
        return {"note": "queue depth moved to RabbitMQ management API (M3)"}

    @staticmethod
    async def get_consumer_status() -> Dict[str, Any]:
        worker_age = await _heartbeat_age("ap:taskiq:worker:heartbeat")
        return {
            "is_running": 0 <= worker_age <= _HEARTBEAT_MAX_AGE,
            "heartbeat_age_s": worker_age,
            "processed_count": None,  # 消费计数以 EventRecord 状态为准（可按需聚合）
        }
