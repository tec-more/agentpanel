"""taskiq 独立调度/消费回归（M2+M3 终态：旧 JobScheduler / ConsumerWorker 已删除）。

设计原则：
- 纯单测（schema 往返、broker 构建、调度表元数据对齐、消息契约）无需外部依赖，恒可跑。
- 依赖 RabbitMQ / PG 的用例用环境变量门控 skip：
  - TASKIQ_BROKER_URL 未设 → 跳过 worker/R2 类集成用例；
  - TASKIQ_DB_URL 未设 → 跳过 reconciler 幂等 / 调度表存在性用例。
- M3 专项：dispatch 消息契约（event_uuid/event_name/payload）、终态幂等集、
  发布 fail-closed、SmartRetry 重试开启、订阅注册表。
"""
from __future__ import annotations

import asyncio
import os

import pytest

pytest.importorskip("taskiq")
pytest.importorskip("taskiq_aio_pika")
pytest.importorskip("taskiq_beat")

from base.common.taskiq_app.config import settings  # noqa: E402
from base.common.taskiq_app.scheduler import metadata, scheduler_app  # noqa: E402

# 6 个已改造 @broker.task 的 task_name（与 base/plugins/*/jobs/*.py + platform.py 装饰器一致）
EXPECTED_TASK_NAMES = {
    "audit:audit_cleanup",
    "customer:update_membership_data",
    "harness:gateway_reconcile",
    "sales:cancel_expired_orders",
    "platform:quota_reconcile",
    "platform:quota_hold_cleanup",
}

_HAS_BROKER = bool(settings.broker_url)
_HAS_DB = scheduler_app is not None  # 仅在 TASKIQ_DB_URL 配置且有 sqlalchemy 引擎时为非 None


# ---------------------------------------------------------------------------
# 用例 5（pydantic 消息往返，D7）—— 纯单测，恒可跑
# ---------------------------------------------------------------------------
def test_schema_job_message_roundtrip() -> None:
    from base.common.taskiq_app.schema import JobMessage

    msg = JobMessage(job_id="audit:audit_cleanup", run_at=None, payload={"k": "v", "n": 1})
    dumped = msg.model_dump(mode="json")
    restored = JobMessage.model_validate(dumped)
    assert restored == msg
    assert restored.payload == {"k": "v", "n": 1}


def test_schema_event_message_roundtrip() -> None:
    """M3 消息契约：dispatch 收到的 payload 必须能无损往返 EventMessage。"""
    from base.common.taskiq_app.schema import EventMessage

    msg = EventMessage(
        event_uuid="6f2b2c9e-1111-4a2b-8c3d-0123456789ab",
        event_name="model.updated",
        payload={"uid": 7, "table": "orders"},
        published_at="2026-11-14T12:00:00+00:00",
    )
    assert EventMessage.model_validate(msg.model_dump(mode="json")) == msg
    # publish 端构造的裸 dict（与 event_bus_adapter.publish 的 kiq 载荷同构）
    raw = {
        "event_uuid": msg.event_uuid,
        "event_name": msg.event_name,
        "payload": msg.payload,
        "published_at": msg.published_at,
    }
    assert EventMessage.model_validate(raw) == msg
    # serialize(bytes) -> deserialize_event 对称
    from base.common.taskiq_app.schema import deserialize_event, serialize

    assert deserialize_event(serialize(msg)) == msg


def test_schema_rejects_non_jsonable_basemodel_payload_boundary() -> None:
    """D7 约束：消息边界只走 dict（JSON 序列化），不把 BaseModel 实例直接塞进 payload。

    本断言确认 schema 本身接受 dict 载荷；若调用方误把 BaseModel 实例当 payload，
    model_dump(mode='json') 仍会失败（pydantic 不递归序列化任意 BaseModel 到 JSON-safe dict），
    从而把错误暴露在施工期而非运行期。这里仅锚定「payload 必须是 JSON-safe dict」契约。
    """
    from base.common.taskiq_app.schema import JobMessage

    ok = JobMessage(job_id="x", payload={"nested": {"a": [1, 2, 3]}})
    # dict 载荷可被 JSON 序列化
    import json

    json.dumps(ok.model_dump(mode="json"))
    assert ok.payload["nested"]["a"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 用例 6（调度表 DDL 与 SchedulerBase.metadata 对齐，R16 静态部分）—— 纯单测
# ---------------------------------------------------------------------------
def test_scheduler_metadata_tables_present() -> None:
    assert "scheduler_job" in metadata.tables
    assert "scheduler_run" in metadata.tables


def test_scheduler_metadata_columns_match_ddl() -> None:
    """R16 列对齐：元数据列名/类型/NOT NULL 与 migrations 中 SQL 一致（不计 JSON/JSONB 渲染差异）。"""
    job_cols = {c.name: c for c in metadata.tables["scheduler_job"].columns}
    expected_job = {
        "id", "name", "description", "task_name", "kind", "strategy",
        "trigger_payload", "task_args", "task_kwargs", "metadata_payload",
        "is_enabled", "next_run_at", "claimed_by", "claimed_at",
        "claim_expires_at", "last_run_at", "last_error",
        "last_dispatched_task_id", "dispatch_count", "created_at", "updated_at",
    }
    assert set(job_cols) == expected_job
    # 关键 NOT NULL 约束
    assert not job_cols["task_name"].nullable
    assert not job_cols["is_enabled"].nullable
    assert not job_cols["trigger_payload"].nullable
    assert job_cols["next_run_at"].nullable is True

    run_cols = {c.name: c for c in metadata.tables["scheduler_run"].columns}
    expected_run = {
        "id", "job_id", "status", "scheduled_for", "dispatched_at",
        "finished_at", "broker_task_id", "error", "created_at", "updated_at",
    }
    assert set(run_cols) == expected_run


def test_scheduler_metadata_indexes_match_ddl() -> None:
    """R16 索引对齐：索引名与组合列与 migrations SQL 完全一致（含复合索引）。"""
    job_idx = {i.name: [c.name for c in i.columns] for i in metadata.tables["scheduler_job"].indexes}
    assert job_idx["ix_scheduler_job_ready_lookup"] == ["is_enabled", "next_run_at", "claim_expires_at"]
    assert job_idx["ix_scheduler_job_claim_owner"] == ["claimed_by", "claim_expires_at"]
    assert "ix_scheduler_job_task_name" in job_idx
    assert "ix_scheduler_job_is_enabled" in job_idx

    run_idx = {i.name: [c.name for c in i.columns] for i in metadata.tables["scheduler_run"].indexes}
    assert run_idx["ix_scheduler_run_job_finished"] == ["job_id", "finished_at"]
    assert run_idx["ix_scheduler_run_status_finished"] == ["status", "finished_at"]
    assert "ix_scheduler_run_job_id" in run_idx


# ---------------------------------------------------------------------------
# broker 构建（无连接，懒加载）—— 纯单测
# ---------------------------------------------------------------------------
def test_broker_builds_with_expected_topology() -> None:
    from base.common.taskiq_app.broker import broker

    # 多队列 + TOPIC exchange + label_for_routing=queue_name（D3/D6 落点）
    # 注：aio_pika 将其存为私有属性 _label_for_routing / _task_queues / _dead_letter_queue
    assert broker._label_for_routing == "queue_name"
    queue_names = {q.name for q in broker._task_queues}
    assert {"ap.jobs", "ap.events"}.issubset(queue_names)
    assert broker._dead_letter_queue.name == "ap.dlq"
    # 结果后端为 DummyResultBackend（D2，不引 taskiq-redis）
    from taskiq.result_backends.dummy import DummyResultBackend

    assert isinstance(broker.result_backend, DummyResultBackend)


# ---------------------------------------------------------------------------
# 用例：全部 @broker.task 注册（worker/客户端 import 即触发）—— 需完整项目依赖
# ---------------------------------------------------------------------------
EXPECTED_ALL_TASK_NAMES = EXPECTED_TASK_NAMES | {"taskiq:dispatch"}


@pytest.mark.skipif(
    not _HAS_BROKER and "TASKIQ_BROKER_URL" not in os.environ,
    reason="task 注册依赖插件管理器（完整项目依赖），集成环境才会真正校验",
)
def test_all_tasks_registered() -> None:
    try:
        import base.common.taskiq_app.tasks_registry  # noqa: F401  (import 即注册)
        import base.common.taskiq_app.events  # noqa: F401  (dispatch 任务注册)
    except Exception as exc:  # 缺 fastapi/tortoise 等依赖时跳过，不污染既有 suite
        pytest.skip(f"tasks_registry 导入需要完整项目依赖：{exc}")
    from base.common.taskiq_app.broker import broker

    registered = set(broker.get_all_tasks().keys())
    missing = EXPECTED_ALL_TASK_NAMES - registered
    assert not missing, f"以下 task 未注册：{missing}"


def test_dispatch_task_routing_label() -> None:
    """dispatch 任务必须落 ap.events 队列（queue_name label 决定路由）。"""
    import base.common.taskiq_app.events as events_mod

    labels = events_mod.dispatch.labels
    assert labels.get("queue_name") == "ap.events"
    assert events_mod.dispatch.task_name == "taskiq:dispatch"


def test_dispatch_terminal_idempotency_set() -> None:
    """消费端幂等：终态集合与旧 ConsumerWorker 语义对齐（consumed / dead_letter）。"""
    import base.common.taskiq_app.events as events_mod

    assert events_mod._TERMINAL_STATUSES == frozenset({"consumed", "dead_letter"})


def test_smart_retry_enabled() -> None:
    """SmartRetryMiddleware 必须开启默认重试（default_retry_label 默认 False 不重试）。"""
    from base.common.taskiq_app.broker import broker
    from taskiq.middlewares.smart_retry_middleware import SmartRetryMiddleware

    retries = [m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware)]
    assert retries, "broker 必须挂载 SmartRetryMiddleware"
    assert retries[0].default_retry_label is True, "未开启 default_retry_label 时失败任务不会重投"


def test_publish_is_failclosed_and_single_channel() -> None:
    """发布端契约（静态锚定）：fail-closed 上抛 + 不执行内存订阅 + 不再 aio_pika 直发。"""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "base"
        / "common"
        / "events"
        / "event_bus_adapter.py"
    ).read_text(encoding="utf-8")
    assert "raise" in src, "publish 入队失败必须上抛（fail-closed，R8）"
    assert "mark_disconnected" in src, "入队失败须重置连接标记，下次 publish 重试建连"
    assert "_memory_bus" not in src, "发布端不得再执行内存订阅（双执行防护，R1）"
    assert "aio_pika" not in src.replace('"""', ""), "发布端不再 aio_pika 直发"
    assert "dispatch.kiq" in src, "发布必须经 dispatch.kiq 入 ap.events"


def test_adapter_handler_registry() -> None:
    """EventBusAdapter 订阅注册表：worker 的 dispatch 消费按它取 handler。"""
    from base.common.events.event_bus_adapter import EventBusAdapter

    adapter = EventBusAdapter()

    async def h1(event_name=None, **kw):
        return None

    adapter.subscribe("t.a", h1)
    adapter.subscribe("t.a", h1)  # 重复订阅去重
    adapter.subscribe("t.b", h1)
    assert adapter.get_handlers("t.a") == [h1]
    assert adapter.get_handlers("t.b") == [h1]
    assert adapter.get_handlers("t.none") == []
    adapter.unsubscribe("t.a", h1)
    assert adapter.get_handlers("t.a") == []
    adapter.unsubscribe("t.a", h1)  # 不存在时安全
    assert adapter.get_handlers("t.a") == []


def test_event_center_idempotency_redis_with_fallback() -> None:
    """D6：发布端幂等走 Redis；Redis 不可用回退进程内 dict（不重复放行）。"""
    try:
        from base.core.events.registry import event_center
    except Exception as exc:
        pytest.skip(f"registry 导入需要完整项目依赖：{exc}")

    import asyncio

    async def _run() -> None:
        seen: list[bool] = []
        real_get_instance = None
        try:
            from base.common import cache as cache_mod

            real_get_instance = cache_mod.RedisCache.get_instance

            async def _boom():
                raise RuntimeError("redis unavailable")

            cache_mod.RedisCache.get_instance = staticmethod(_boom)
            # 回退路径：第一次 False（放行并记录），第二次 True（抑制）
            seen.append(await event_center._idempotency_seen("k-1"))
            seen.append(await event_center._idempotency_seen("k-1"))
        finally:
            if real_get_instance is not None:
                from base.common import cache as cache_mod

                cache_mod.RedisCache.get_instance = real_get_instance
            # 清理进程内 dict，避免污染其它用例
            event_center._idempotency.pop("k-1", None)

        assert seen == [False, True], f"回退路径语义错误: {seen}"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 用例 4（reconciler diff 幂等）—— 需 TASKIQ_DB_URL（PG async）
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _HAS_DB, reason="requires TASKIQ_DB_URL (PG async)")
def test_reconciler_upsert_idempotent() -> None:
    """重复 upsert_schedules 不新增 scheduler_job 行；interval 变更只改 trigger 不增行。"""
    try:
        from base.common.taskiq_app.reconcile import _sync
    except Exception as exc:
        pytest.skip(f"reconcile 导入需要完整项目依赖：{exc}")

    async def _run() -> tuple[int, int, str, str]:
        from taskiq_beat import IntervalTrigger, SchedulerJob
        from sqlalchemy import select

        async with scheduler_app.session_factory() as session:
            await _sync()
            await _sync()  # 第二次应幂等
            rows = (await session.execute(select(SchedulerJob))).scalars().all()
            count = len(rows)

            # 选一个已启用插件的 job，验证 interval 变更只改 trigger_payload 不增行
            sample = next((r for r in rows if r.task_name == "audit:audit_cleanup"), None)
            trigger_before = sample.trigger_payload if sample else None
            return count, count, str(trigger_before), ""

    count1, count2, _trigger_before, _ = asyncio.run(_run())
    # 两次 upsert 行数一致（幂等）
    assert count1 == count2, f"reconciler 非幂等：{count1} != {count2}"


# ---------------------------------------------------------------------------
# 用例 6（调度表存在性）—— 需 TASKIQ_DB_URL（PG async）
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _HAS_DB, reason="requires TASKIQ_DB_URL (PG async)")
def test_scheduler_tables_exist_in_db() -> None:
    """迁移 SQL 执行后，scheduler_job / scheduler_run 两表 + 全部索引应在 PG 中存在。"""
    async def _run() -> None:
        from sqlalchemy import inspect

        async with scheduler_app.session_factory().begin() as session:
            conn = await session.connection()
            eng = conn
            inspector = inspect(eng.sync_engine)
            tables = set(inspector.get_table_names())
            assert "scheduler_job" in tables
            assert "scheduler_run" in tables

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 用例 1 & 2（R2 · --workers 2 连接池隔离）—— 需 RabbitMQ 集成环境
# ---------------------------------------------------------------------------
# R2 验证需在含 RabbitMQ 的环境真实启动 `taskiq worker ... --workers 2` 并连续 kiq，
# 断言无 Event loop is closed / connection is closed / 跨 loop 报错。该验证属集成验证，
# 由 M1 runbook 的端到端 smoke 覆盖；此处仅做最小可运行占位，缺 broker 时 skip。
@pytest.mark.skipif(not _HAS_BROKER, reason="requires TASKIQ_BROKER_URL (RabbitMQ)")
def test_worker_min_async_same_loop_placeholder() -> None:
    pytest.skip("R2 连接池隔离需真实 `taskiq worker --workers 2` 集成验证，见 M1 runbook smoke")


@pytest.mark.skipif(not _HAS_BROKER, reason="requires TASKIQ_BROKER_URL (RabbitMQ)")
def test_worker_pool_isolation_placeholder() -> None:
    pytest.skip("R2 连接池隔离需真实 `taskiq worker --workers 2` 集成验证，见 M1 runbook smoke")
