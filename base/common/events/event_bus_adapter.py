"""EventBusAdapter：发布端唯一入口（Transactional Outbox）。

改造（2026-11-15，Outbox/Inbox）
--------------------------------
``publish`` **只写数据库**：在事务内落一条 ``EventRecord(status=pending)``，
由 ``platform:outbox_relay`` 平台作业异步投递进 ``ap.events``。不再连消息中间件、
不再本地执行订阅者、不再有"入队失败上抛"的路径。

为什么必须这样：RabbitMQ 无法参与 PostgreSQL 事务（无 XA，publisher confirm
也不能进 DB 事务）。把「业务写库 + 消息记录」放进同一个 DB 事务，DB→MQ 由
Outbox 保证不丢（可能重复），MQ→DB 由 Inbox + 状态机保证不重复执行，
端到端是**最终一致 / 等效 exactly-once**，不是强一致。

事务复用：Tortoise ``connections.get()`` 走 contextvar，调用方若已处于
``@atomic()`` / ``in_transaction()`` 中，本模块的 ``in_transaction()`` 会自动
复用同一连接（asyncpg 下表现为 savepoint）；否则新建事务。因此现有 20+ 业务
调用点无需改代码即可获得原子性。

幂等：``event_records.idempotency_key`` 唯一约束，替代原 Redis 300s 键，
使「幂等判定 + 消息落库」同事务。唯一冲突在 savepoint 内回滚，不会把调用方
外层事务打成 aborted 状态。

载荷安全（2026-11-15 后台观测能力补齐）：所有载荷在落库前经
``payload_contract.sanitize_payload`` 脱敏 + 体积保护。业务直调本入口不做
严格校验（否则一个含 ``token`` 的载荷就会回滚整个业务事务），只做遮蔽；
后台手动发布的严格拒绝语义仍由 ``event_center.publish`` 承担。

跨模块串联（2026-11-15）：``trace_id`` 从请求上下文 ``base.common.context``
继承（TraceMiddleware 注入），或由调用方以 ``_trace_id`` 控制字段显式传入；
与 ``audit_log`` / ``audit_input_layer`` / ``audit_output_layer`` 同源，后台
事件详情据此回查原始 HTTP 请求与响应。无请求上下文（定时任务/作业）时为 NULL。

订阅注册表 ``_handler_registry`` 保留：由 ``task/`` 目录 ``@ap_subscribe``
声明的注册函数与事件中心 ``bind_manual`` 填充。app 进程填充它仅为生产探针注册
（发布端不消费）；真正的消费发生在 taskiq worker 的 ``dispatch`` 任务。
"""
import uuid
import logging
from typing import Dict, Any, Callable, List
from datetime import datetime, timezone
from decimal import Decimal

from base.common.context import get_current_trace_id
from base.common.events.payload_contract import sanitize_payload

logger = logging.getLogger(__name__)


class EventBusAdapter:
    def __init__(self):
        # 进程内订阅注册表：event_name -> [handler]。
        # 由 task/ 目录 @ap_subscribe 注册函数与 event_center.bind_manual 填充；
        # 唯一消费方是 taskiq worker 的 dispatch 任务（get_handlers）。
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
    # 发布（Outbox：只落库，不触网）
    # ------------------------------------------------------------------
    async def publish(
        self,
        event_name: str,
        *,
        idempotency_key: str | None = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """业务事务内写一条待投递消息；返回发布结果（含 event_uuid）。

        - 事务：外层 ``@atomic()`` 自动复用；唯一键冲突只回滚 savepoint。
        - 投递：完全交给 ``platform:outbox_relay``，MQ 不可用不影响本次落库。
        - 返回：``{"published": bool, "duplicate": bool, "event_uuid": str|None}``
        """
        source_module = kwargs.pop("_source_module", None)
        trace_id = kwargs.pop("_trace_id", None) or get_current_trace_id()
        event_uuid = str(uuid.uuid4())
        # 脱敏 + 体积保护 + 纯 JSON 化：业务直调路径不能因载荷问题打断事务。
        payload = sanitize_payload(self._serialize_payload(kwargs))
        now = datetime.now(timezone.utc)

        from tortoise.exceptions import IntegrityError
        from tortoise.transactions import in_transaction

        from base.common.events.models.event_record import EventRecord

        try:
            # 嵌套 in_transaction 在已有事务内是 savepoint：唯一键冲突只回滚
            # 该 savepoint，不会污染调用方的业务事务。
            async with in_transaction():
                await EventRecord.create(
                    event_uuid=event_uuid,
                    event_name=event_name,
                    payload=payload,
                    status="pending",
                    idempotency_key=idempotency_key,
                    published_at=now,
                    source_module=source_module,
                    trace_id=trace_id,
                )
        except IntegrityError:
            logger.info(f"事件 {event_name} 幂等键重复，跳过落库: {idempotency_key}")
            return {
                "published": False,
                "duplicate": True,
                "event_uuid": None,
                "idempotency_key": idempotency_key,
            }

        return {
            "published": True,
            "duplicate": False,
            "event_uuid": event_uuid,
            "idempotency_key": idempotency_key,
            "status": "pending",
        }

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
    # 生命周期（app 进程已无 broker 客户端连接；保留方法供 lifespan 调用）
    # ------------------------------------------------------------------
    async def initialize(self):
        """Outbox 后 app 发布端不建写连接，仅保留生命周期钩子。"""
        logger.info("EventBusAdapter初始化完成(Outbox：发布只落库，投递由 relay 负责)")

    async def shutdown(self):
        """Outbox 后 app 发布端无连接需释放。"""
        logger.info("EventBusAdapter关闭完成(Outbox：无客户端连接)")
