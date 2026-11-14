"""单 `AioPikaBroker` 定义 + 中间件（jobs / events 两队列同 broker，专用 vhost）。

要点（基于 taskiq 0.13.0 / taskiq-aio-pika 0.6.1 源码核实）：
- 声明多个 `task_queues` 时，每个 `@broker.task` 必须带 `queue_name` label（= routing key），
  aio-pika 用它作为 RabbitMQ routing key 把消息路由到对应队列；遗漏则投递无路由。
- 使用 TOPIC exchange（默认），队列以 `routing_key` 绑定，topic 匹配容错且足够；
  无需 DIRECT 的严格枚举校验。
- 结果后端用 `DummyResultBackend`（D2 决策，不引 taskiq-redis）。
- 中间件：`SmartRetryMiddleware`（M1 取配置默认值）。
"""
from __future__ import annotations

from aio_pika import ExchangeType
from loguru import logger
from taskiq import AsyncBroker
from taskiq.middlewares.smart_retry_middleware import SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker, Exchange, Queue, QueueType

from .config import settings


def _resolve_url() -> str | None:
    """broker 连接串：优先 TASKIQ_BROKER_URL secret；dev 未配置时回退 [rabbitmq] 段。

    回退优先级与 prepare-secrets.ps1 一致：taskiq_vhost/taskiq_username/
    taskiq_password 专用键 -> virtual_host/username/password 共用键 -> vhost
    缺省 `agentpanel`（部署侧事实，deploy/rabbitmq/definitions.json）。
    生产部署仍应通过 TASKIQ_BROKER_URL_FILE 注入专用 vhost 连接串（D6）。
    """
    if settings.broker_url:
        return settings.broker_url
    try:
        from base.common.setting import settings as app_settings

        if app_settings.RABBITMQ_ENABLED:
            from urllib.parse import quote

            vhost = (
                app_settings.RABBITMQ_TASKIQ_VHOST
                or app_settings.RABBITMQ_VIRTUAL_HOST
                or "agentpanel"
            )
            username = (
                app_settings.RABBITMQ_TASKIQ_USERNAME
                or app_settings.RABBITMQ_USERNAME
            )
            password = (
                app_settings.RABBITMQ_TASKIQ_PASSWORD
                or app_settings.RABBITMQ_PASSWORD
            )
            return (
                f"amqp://{quote(username, safe='')}:"
                f"{quote(password, safe='')}"
                f"@{app_settings.RABBITMQ_HOST}:{app_settings.RABBITMQ_PORT}/"
                f"{quote(vhost, safe='')}"
            )
    except Exception as exc:  # 配置不可用时交给 taskiq 默认 URL（连接失败会 fail-closed 显形）
        logger.warning(f"[taskiq broker] [rabbitmq] 回退 URL 构造失败: {exc}")
    return None


def _build_broker() -> AioPikaBroker:
    # 不传 result_backend：AioPikaBroker 默认即 DummyResultBackend（D2 决策，不引
    # taskiq-redis）。显式传构造参数会触发 taskiq 0.13 的弃用告警，故省略。
    broker = AioPikaBroker(
        url=_resolve_url(),
        exchange=Exchange(
            name=settings.exchange,
            type=ExchangeType.TOPIC,
            durable=True,
            declare=True,
        ),
        task_queues=[
            Queue(
                name=settings.jobs_queue,
                routing_key=settings.jobs_queue,
                type=QueueType.CLASSIC,
                durable=True,
            ),
            Queue(
                name=settings.events_queue,
                routing_key=settings.events_queue,
                type=QueueType.CLASSIC,
                durable=True,
            ),
        ],
        dead_letter_queue=Queue(
            name=settings.dlq_queue,
            routing_key=settings.dlq_queue,
            type=QueueType.CLASSIC,
            durable=True,
        ),
        label_for_routing="queue_name",
    )
    broker.add_middlewares(
        SmartRetryMiddleware(
            default_retry_count=settings.retry_max,
            default_delay=float(settings.retry_delay),
            # 关键：default_retry_label 默认 False（不重试）。置 True 使失败任务
            # 经指数退避重投（事件失败上抛 → dispatch 重入；作业失败自动补试）。
            default_retry_label=True,
            use_delay_exponent=True,
        )
    )
    return broker


broker: AsyncBroker = _build_broker()

logger.info(
    f"[taskiq broker] 已构建：exchange={settings.exchange} "
    f"queues=[{settings.jobs_queue}, {settings.events_queue}] dlq={settings.dlq_queue}"
)

# ---------------------------------------------------------------------------
# 客户端模式连接管理（app 进程 publish → kiq 用；worker 进程由 CLI 自行 startup）
# ---------------------------------------------------------------------------
# taskiq-aio-pika 的 kick 在 write_channel 未初始化时抛 NoStartupError，
# 因此 app 进程必须在首次 publish 前调用 startup()（客户端模式只建写连接）。
_startup_done = False


async def ensure_started() -> None:
    """确保 broker 客户端连接就绪（幂等；失败置回未就绪，下次 publish 重试）。

    连接失败向上抛出 → EventBusAdapter.publish fail-closed（调用方/网关得到
    明确错误，而非静默丢事件）。
    """
    global _startup_done
    if _startup_done:
        return
    await broker.startup()
    _startup_done = True
    logger.info("[taskiq broker] 客户端连接就绪（publish 可用）")


async def mark_disconnected() -> None:
    """连接失效时重置标记，让下一次 publish 重新尝试建连。"""
    global _startup_done
    _startup_done = False


async def shutdown_client() -> None:
    """app 进程关闭期断开客户端连接（worker 进程不经过本函数）。"""
    global _startup_done
    if not _startup_done:
        return
    try:
        await broker.shutdown()
    except Exception as exc:  # 关闭失败不阻断退出
        logger.warning(f"[taskiq broker] 客户端连接关闭失败（忽略）: {exc}")
    _startup_done = False
    logger.info("[taskiq broker] 客户端连接已关闭")
