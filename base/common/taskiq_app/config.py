"""taskiq 服务配置（§2 配置段落地）。

仅读 `TASKIQ_*` 环境变量 + `_FILE` secret（复用 `packages.common.config.read_env_value`）。
连接串只走 secret，不写入 `config.conf`。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from packages.common.config import read_env_value


@dataclass(frozen=True)
class TaskiqSettings:
    """taskiq 服务运行配置（全部带默认值，缺失不报错）。"""

    broker_url: str = ""  # amqp 完整 URL（含专用 vhost），secret
    db_url: str = ""  # PG async URL（postgresql+asyncpg://），secret
    vhost: str = "agentpanel"
    exchange: str = "ap.taskiq"
    jobs_queue: str = "ap.jobs"
    events_queue: str = "ap.events"
    dlq_queue: str = "ap.dlq"
    result_backend: str = "dummy"
    ack_type: str = "when_executed"
    workers: int = 2
    max_async_tasks: int = 2
    max_prefetch: int = 0
    shutdown_timeout: float = 12.0
    wait_tasks_timeout: float = 8.0
    beat_sync_interval: float = 1.0
    beat_idle_sleep: float = 0.2
    reconcile_interval: float = 5.0
    beat_scheduler_id: Optional[str] = None  # 留空用默认随机（uuid4），禁止钉固定值（§5.1）
    lock_ttl: int = 60
    idempotency_ttl: int = 300
    event_handler_timeout: float = 30.0
    job_timeout: float = 60.0
    retry_max: int = 3
    retry_delay: int = 5
    redis_key_prefix: str = "ap:taskiq:"
    redis_db_taskiq: int = 0
    subscription_channel: str = "ap:taskiq:subscription"
    metrics_port: int = 9091
    run_history_retention_days: Optional[int] = None

    @classmethod
    def load(cls) -> "TaskiqSettings":
        return cls(
            broker_url=read_env_value("TASKIQ_BROKER_URL", "str", secret=True, default=""),
            db_url=read_env_value("TASKIQ_DB_URL", "str", secret=True, default=""),
            vhost=read_env_value("TASKIQ_VHOST", "str", default="agentpanel"),
            exchange=read_env_value("TASKIQ_EXCHANGE", "str", default="ap.taskiq"),
            jobs_queue=read_env_value("TASKIQ_JOBS_QUEUE", "str", default="ap.jobs"),
            events_queue=read_env_value("TASKIQ_EVENTS_QUEUE", "str", default="ap.events"),
            dlq_queue=read_env_value("TASKIQ_DLQ_QUEUE", "str", default="ap.dlq"),
            result_backend=read_env_value("TASKIQ_RESULT_BACKEND", "str", default="dummy"),
            ack_type=read_env_value("TASKIQ_ACK_TYPE", "str", default="when_executed"),
            workers=read_env_value("TASKIQ_WORKERS", "int", default=2),
            max_async_tasks=read_env_value("TASKIQ_MAX_ASYNC_TASKS", "int", default=2),
            max_prefetch=read_env_value("TASKIQ_MAX_PREFETCH", "int", default=0),
            shutdown_timeout=read_env_value("TASKIQ_SHUTDOWN_TIMEOUT", "float", default=12.0),
            wait_tasks_timeout=read_env_value("TASKIQ_WAIT_TASKS_TIMEOUT", "float", default=8.0),
            beat_sync_interval=read_env_value("TASKIQ_BEAT_SYNC_INTERVAL", "float", default=1.0),
            beat_idle_sleep=read_env_value("TASKIQ_BEAT_IDLE_SLEEP", "float", default=0.2),
            reconcile_interval=read_env_value("TASKIQ_RECONCILE_INTERVAL", "float", default=5.0),
            beat_scheduler_id=read_env_value("TASKIQ_BEAT_SCHEDULER_ID", "str", default=None),
            lock_ttl=read_env_value("TASKIQ_LOCK_TTL", "int", default=60),
            idempotency_ttl=read_env_value("TASKIQ_IDEMPOTENCY_TTL", "int", default=300),
            event_handler_timeout=read_env_value("TASKIQ_EVENT_HANDLER_TIMEOUT", "float", default=30.0),
            job_timeout=read_env_value("TASKIQ_JOB_TIMEOUT", "float", default=60.0),
            retry_max=read_env_value("TASKIQ_RETRY_MAX", "int", default=3),
            retry_delay=read_env_value("TASKIQ_RETRY_DELAY", "int", default=5),
            redis_key_prefix=read_env_value("TASKIQ_REDIS_KEY_PREFIX", "str", default="ap:taskiq:"),
            redis_db_taskiq=read_env_value("TASKIQ_REDIS_DB", "int", default=0),
            subscription_channel=read_env_value(
                "TASKIQ_SUBSCRIPTION_CHANNEL", "str", default="ap:taskiq:subscription"
            ),
            metrics_port=read_env_value("TASKIQ_METRICS_PORT", "int", default=9091),
            run_history_retention_days=read_env_value(
                "TASKIQ_RUN_HISTORY_RETENTION_DAYS", "int", default=None
            ),
        )


settings: TaskiqSettings = TaskiqSettings.load()
