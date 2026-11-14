"""EventBusAdapter：发布端唯一入口（M3 后）。

M3 改造（取代旧的 RabbitMQ 直发 + 内存总线双通道）：
- ``publish`` = 写 ``EventRecord(published)`` + ``dispatch.kiq(...)`` 入 ``ap.events``
  队列；**不再本地执行内存订阅**（消除 handler 双执行的第一正确性前提），
  **不再保留降级静默丢路径**（broker 不可用 → fail-closed 上抛，调用方得到明确错误）。
- 订阅注册表 ``_handler_registry`` 保留：由各插件 ``register_ref`` 与事件中心
  ``bind_manual`` 填充。app 进程填充它仅为生产探针注册（publish 端不再消费）；
  真正的消费发生在 taskiq worker 进程（``taskiq_app.events.dispatch`` 按本注册表
  取 handler 执行，worker 启动期同样执行 register_ref / bind_manual 构建注册表）。
- 连接管理 = taskiq broker 客户端模式（``ensure_started`` / ``shutdown_client``），
  旧的 ``RabbitMQConnectionManager`` / ConsumerWorker 已删除。
"""
import uuid
import logging
from typing import Dict, Any, Callable, List
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class EventBusAdapter:
    def __init__(self):
        # 进程内订阅注册表：event_name -> [handler]。
        # 由 register_ref（各插件注册函数）与 event_center.bind_manual 填充；
        # M3 后唯一消费方是 taskiq worker 的 dispatch 任务（get_handlers）。
        self._handler_registry: Dict[str, List[Callable]] = {}

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------
    @staticmethod
    def _serialize_payload(kwargs: Dict[str, Any]) -> Dict[str, Any]:
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

    # ------------------------------------------------------------------
    # 发布（fail-closed）
    # ------------------------------------------------------------------
    async def publish(self, event_name: str, **kwargs):
        """写 EventRecord(published) 并把事件消息 kiq 进 ``ap.events``。

        - 入队失败 → 异常上抛（fail-closed，R8：不保留静默丢事件的降级分支）。
        - 不执行任何本地订阅（第一正确性前提：发布端与消费端物理分离）。
        """
        event_uuid = str(uuid.uuid4())
        payload = self._serialize_payload(kwargs)
        now = datetime.now(timezone.utc)
        source_module = kwargs.pop("_source_module", None)

        from base.common.events.models.event_record import EventRecord

        await EventRecord.create(
            event_uuid=event_uuid,
            event_name=event_name,
            payload=payload,
            status="published",
            published_at=now,
            source_module=source_module,
        )

        # broker 客户端连接惰性保证（幂等；失败上抛 → fail-closed）
        from base.common.taskiq_app.broker import ensure_started

        await ensure_started()

        from base.common.taskiq_app.events import dispatch

        try:
            await dispatch.kiq(
                {
                    "event_uuid": event_uuid,
                    "event_name": event_name,
                    "payload": payload,
                    "published_at": now.isoformat(),
                }
            )
        except Exception as exc:
            logger.error(f"事件 {event_name}({event_uuid}) 入队失败(fail-closed): {exc}")
            # 标记断连，下一次 publish 会重新建连；异常上抛让调用方明确失败
            from base.common.taskiq_app.broker import mark_disconnected

            await mark_disconnected()
            raise

    # ------------------------------------------------------------------
    # 订阅注册表（worker 消费取 handler；app 进程注册生产探针）
    # ------------------------------------------------------------------
    def subscribe(self, event_name: str, handler: Callable):
        if event_name not in self._handler_registry:
            self._handler_registry[event_name] = []
        if handler not in self._handler_registry[event_name]:
            self._handler_registry[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Callable):
        if event_name in self._handler_registry and handler in self._handler_registry[event_name]:
            self._handler_registry[event_name].remove(handler)

    def get_handlers(self, event_name: str) -> List[Callable]:
        return self._handler_registry.get(event_name, [])

    # ------------------------------------------------------------------
    # 生命周期（app 进程：连接 taskiq broker；worker 进程由 CLI startup）
    # ------------------------------------------------------------------
    async def initialize(self):
        """app 启动期预热 broker 客户端连接（失败不阻断启动，publish 时重试）。"""
        try:
            from base.common.taskiq_app.broker import ensure_started

            await ensure_started()
            logger.info("EventBusAdapter初始化完成(taskiq broker 已连接)")
        except Exception as e:
            logger.warning(f"taskiq broker 连接失败(启动期忽略，publish 时将重试): {e}")

    async def shutdown(self):
        try:
            from base.common.taskiq_app.broker import shutdown_client

            await shutdown_client()
        except Exception as e:
            logger.warning(f"EventBusAdapter关闭失败: {e}")
        logger.info("EventBusAdapter已关闭")
