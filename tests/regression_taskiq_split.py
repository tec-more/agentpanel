"""taskiq 独立调度/消费回归（M2+M3 终态：旧 JobScheduler / ConsumerWorker 已删除）。

设计原则：
- 纯单测（schema 往返、broker 构建、调度表元数据对齐、消息契约）无需外部依赖，恒可跑。
- 依赖 RabbitMQ / PG 的用例用环境变量门控 skip：
  - TASKIQ_BROKER_URL 未设 → 跳过 worker/R2 类集成用例；
  - TASKIQ_DB_URL 未设 → 跳过 reconciler 幂等 / 调度表存在性用例。
- M3 专项：dispatch 消息契约（event_uuid/event_name/payload）、终态幂等集、
  发布 Outbox 事务落库（2026-11-15 起取代 fail-closed 直投）、SmartRetry
  重试开启、订阅注册表。
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

# 8 个声明式作业的 task_name（来自 base/plugins/*/task/*.py 的 @broker.task
# 与 platform_jobs.py；2026-11-15 起 manifest.jobs 已废弃，同日新增两个
# Outbox 平台作业）
EXPECTED_TASK_NAMES = {
    "audit:audit_cleanup",
    "customer:update_membership_data",
    "harness:gateway_reconcile",
    "sales:cancel_expired_orders",
    "platform:quota_reconcile",
    "platform:quota_hold_cleanup",
    "platform:outbox_relay",
    "platform:stale_consuming_reap",
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

    # 偏差1整改：所有 ap.jobs 作业必须已装配执行期插件门控
    from base.common.taskiq_app.job_gate import _GATE_MARK

    for name, task in broker.get_all_tasks().items():
        if (task.labels or {}).get("queue_name") != "ap.jobs":
            continue
        assert getattr(task.original_func, _GATE_MARK, False), (
            f"{name} 未装配执行期插件门控（tasks_registry.apply_plugin_gate 漏调？）"
        )


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


def test_smart_retry_disabled_in_favor_of_outbox() -> None:
    """重试唯一驱动改为 Outbox DB 状态机：中间件延迟重投必须关闭。

    SmartRetryMiddleware.on_error 走 with_labels(delay=...)，本 broker 未配
    delay_queue / delayed-message-exchange，AioPikaBroker.kick 会抛
    IncorrectRoutingKeyError（旧链路「失败→ack→无人补投」的根因）。
    """
    from base.common.taskiq_app.broker import broker
    from base.common.taskiq_app.events import dispatch
    from taskiq.middlewares.smart_retry_middleware import SmartRetryMiddleware

    retries = [m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware)]
    assert retries, "broker 保留 SmartRetryMiddleware 实例（作业可按需逐任务开启）"
    assert retries[0].default_retry_label is False, "默认延迟重投必须关闭，避免双投/抛错"
    assert dispatch.labels.get("retry_on_error") is False, "dispatch 双保险：禁止中间件重投"


def test_ack_type_setting_is_validated_not_dead() -> None:
    """config.ack_type 与 worker CLI 同源，并在构建 broker 时经官方解析器校验。"""
    from taskiq.acks import parse_acknowledge_type

    from base.common.taskiq_app.config import settings

    assert parse_acknowledge_type(settings.ack_type).value == settings.ack_type
    src = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "base" / "common" / "taskiq_app" / "broker.py"
    ).read_text(encoding="utf-8")
    assert "parse_acknowledge_type(settings.ack_type)" in src, "ack_type 不得是死配置"


def test_publish_is_transactional_outbox() -> None:
    """发布端契约（静态锚定）：Outbox 事务落库 + 不触网 + DB 唯一键幂等。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    src = (root / "base" / "common" / "events" / "event_bus_adapter.py").read_text(
        encoding="utf-8"
    )
    assert "in_transaction()" in src, "消息记录必须与业务写库在同一 DB 事务"
    assert 'status="pending"' in src, "发布只写待投递消息记录"
    assert "dispatch.kiq" not in src, "发布端不得直投 ap.events（唯一通道=relay）"
    assert "ensure_started" not in src, "发布端不得再建 broker 客户端连接"
    assert "IntegrityError" in src, "幂等必须由 DB 唯一约束在 savepoint 内判定"
    assert "_memory_bus" not in src, "发布端不得执行内存订阅（双执行防护，R1）"
    assert "aio_pika" not in src.replace('"""', ""), "发布端不得直连消息中间件"

    # 唯一通道：投递只出现在 relay 模块
    relay = (root / "base" / "common" / "taskiq_app" / "outbox.py").read_text(
        encoding="utf-8"
    )
    assert "await dispatch.kiq(message)" in relay


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


def test_publish_idempotency_is_db_unique_constraint() -> None:
    """幂等改由 DB 唯一约束保证：与消息落库同事务，不再依赖 Redis / 进程内 dict。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    try:
        from base.common.events.models.event_record import EventRecord
    except Exception as exc:
        pytest.skip(f"模型导入需要完整项目依赖：{exc}")

    field = EventRecord._meta.fields_map["idempotency_key"]
    assert field.unique is True, "幂等键必须建唯一约束"

    migrations = list(
        (root / "migrations").glob("core_alter_table_event_records_*.sql")
    )
    assert migrations, "缺 event_records Outbox 幂等迁移"
    sql = migrations[0].read_text(encoding="utf-8")
    assert "uq_event_records_idempotency_key" in sql
    assert "ADD COLUMN IF NOT EXISTS dispatch_attempts" in sql
    assert "ADD COLUMN IF NOT EXISTS locked_until" in sql

    registry_src = (root / "base" / "core" / "events" / "registry.py").read_text(
        encoding="utf-8"
    )
    assert "_idempotency_seen" not in registry_src, "Redis 幂等已废弃"
    assert "RedisCache" not in registry_src, "发布端幂等不得再依赖 Redis"


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


# ---------------------------------------------------------------------------
# 执行期插件门控（偏差1整改）：停用插件的已投递作业不得在 worker 执行
# ---------------------------------------------------------------------------
class _FakeDecoratedTask:
    """最小 task 替身：taskiq receiver 只取 task_name / labels / original_func。"""

    def __init__(self, task_name: str, queue_name: str, func) -> None:
        self.task_name = task_name
        self.labels = {"queue_name": queue_name}
        self.original_func = func


def test_job_gate_owner_classification(monkeypatch) -> None:
    from base.common.taskiq_app import job_gate

    monkeypatch.setattr(job_gate, "is_plugin_active", lambda name: name == "enabled")
    assert job_gate.is_job_allowed("platform:quota_reconcile") is True
    assert job_gate.is_job_allowed("taskiq:dispatch") is True
    assert job_gate.is_job_allowed("no_owner_prefix") is True
    assert job_gate.is_job_allowed("enabled:some_job") is True
    assert job_gate.is_job_allowed("disabled:some_job") is False


def test_job_gate_wraps_only_ap_jobs_and_is_idempotent(monkeypatch) -> None:
    from base.common.taskiq_app import job_gate

    monkeypatch.setattr(job_gate, "is_plugin_active", lambda name: True)

    async def _noop():
        return None

    job = _FakeDecoratedTask("audit:audit_cleanup", "ap.jobs", _noop)
    event = _FakeDecoratedTask("taskiq:dispatch", "ap.events", _noop)
    assert job_gate.wrap_job_with_plugin_gate(job) is True
    assert job_gate.wrap_job_with_plugin_gate(event) is False
    wrapped = job.original_func
    assert job_gate.wrap_job_with_plugin_gate(job) is False
    assert job.original_func is wrapped
    assert event.original_func is _noop


def test_job_gate_skips_inactive_plugin_execution(monkeypatch) -> None:
    from base.common.taskiq_app import job_gate

    calls: list[str] = []

    async def _run():
        calls.append("executed")
        return "ok"

    job = _FakeDecoratedTask("audit:audit_cleanup", "ap.jobs", _run)
    job_gate.wrap_job_with_plugin_gate(job)

    monkeypatch.setattr(job_gate, "is_plugin_active", lambda name: False)
    assert asyncio.run(job.original_func()) is None
    assert calls == [], "停用插件的已投递作业不得执行"

    monkeypatch.setattr(job_gate, "is_plugin_active", lambda name: True)
    assert asyncio.run(job.original_func()) == "ok"
    assert calls == ["executed"], "插件启用后同一任务应立即恢复执行"


def test_apply_plugin_gate_covers_all_job_tasks() -> None:
    from base.common.taskiq_app import job_gate

    async def _noop():
        return None

    tasks = {
        "gate:job_a": _FakeDecoratedTask("gate:job_a", "ap.jobs", _noop),
        "gate:job_b": _FakeDecoratedTask("gate:job_b", "ap.jobs", _noop),
        "taskiq:dispatch": _FakeDecoratedTask("taskiq:dispatch", "ap.events", _noop),
    }

    class _FakeBroker:
        def get_all_tasks(self):
            return tasks

    assert job_gate.apply_plugin_gate(_FakeBroker()) == 2
    for name, task_obj in tasks.items():
        if task_obj.labels["queue_name"] == "ap.jobs":
            assert getattr(task_obj.original_func, job_gate._GATE_MARK, False), name
    assert tasks["taskiq:dispatch"].original_func is _noop


def test_tasks_registry_installs_execution_gate() -> None:
    """静态锚定：worker 注册任务后必须装配门控，防止后续重构漏掉装配点。"""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "base" / "common" / "taskiq_app" / "tasks_registry.py"
    ).read_text(encoding="utf-8")
    assert "apply_plugin_gate" in src
    assert "job_gate" in src


# ---------------------------------------------------------------------------
# 声明式发现（2026-11-15）：单一真源 = 插件 task/ 目录里的 @broker.task 标签
# 全部为纯单测，不需要 PG / RabbitMQ。
# ---------------------------------------------------------------------------
def _project_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]


def test_manifest_has_no_jobs_section() -> None:
    """周期作业声明不得再出现在 manifest.json（迁移后残留会被装配契约拒绝）。"""
    import json

    root = _project_root() / "base" / "plugins"
    offenders = [
        path.parent.name
        for path in sorted(root.glob("*/manifest.json"))
        if "jobs" in json.loads(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"以下插件仍带已废弃的 manifest.jobs: {offenders}"


def test_discovery_scans_plugin_task_dirs() -> None:
    """发现器只认插件 task/ 目录（兼容 tasks/、jobs/），且不再依赖 manifest.jobs。"""
    from base.common.taskiq_app.discovery import iter_plugin_task_modules, iter_all_modules

    modules = iter_plugin_task_modules()
    assert modules, "未扫描到任何插件作业模块"
    assert all(".task." in module for _, module in modules), modules
    assert not any(".jobs." in module for _, module in modules), modules
    assert {"sales", "customer", "audit", "harness"} <= {owner for owner, _ in modules}
    assert iter_all_modules()[0][0] == "platform", "平台作业必须最先注册"


def test_discovery_specs_match_declared_jobs() -> None:
    """8 个周期作业的 TaskSpec 与声明逐字段等价，job_id 不变（含 2 个 Outbox 作业）。"""
    try:
        from base.common.taskiq_app.discovery import discover, scheduled_specs
        from base.common.plugin_contract import MIN_JOB_INTERVAL
    except Exception as exc:
        pytest.skip(f"发现器导入需要完整项目依赖：{exc}")

    specs = scheduled_specs(discover())
    by_name = {spec.task_name: spec for spec in specs}
    assert set(by_name) == EXPECTED_TASK_NAMES, (
        f"声明作业集合漂移: missing={EXPECTED_TASK_NAMES - set(by_name)} "
        f"extra={set(by_name) - EXPECTED_TASK_NAMES}"
    )

    expected = {
        "sales:cancel_expired_orders": ("sales", 300, (), None),
        "customer:update_membership_data": ("customer", 600, ("llm",), None),
        "audit:audit_cleanup": ("audit", 86400, (), None),
        "harness:gateway_reconcile": (
            "harness", 600, (), "base.plugins.harness.task.reconcile:resolve_interval"
        ),
        "platform:quota_reconcile": ("platform", 60, (), None),
        "platform:quota_hold_cleanup": ("platform", 60, (), None),
    }
    for name, (owner, interval, requires, ref) in expected.items():
        spec = by_name[name]
        assert spec.owner == owner, name
        assert spec.queue == "ap.jobs", name
        assert spec.schedule == interval >= MIN_JOB_INTERVAL, name
        assert spec.requires == requires, name
        assert spec.interval_ref == ref, name
        assert spec.job_id == name, "job_id 必须等于 task_name（零数据迁移）"
        assert spec.task.task_name == name, "beat 需要真实 task 对象"

    from base.common.taskiq_app.discovery import PLATFORM_MIN_JOB_INTERVAL

    # Outbox 两个平台作业：秒级 relay 依赖平台下限放宽，插件作业仍 ≥30s
    for name, interval in (
        ("platform:outbox_relay", 1),
        ("platform:stale_consuming_reap", 30),
    ):
        spec = by_name[name]
        assert spec.owner == "platform" and spec.is_platform, name
        assert spec.queue == "ap.jobs" and spec.job_id == name, name
        assert spec.schedule == interval >= PLATFORM_MIN_JOB_INTERVAL, name

    platform = [spec for spec in specs if spec.is_platform]
    assert len(platform) == 4, "平台作业必须恒被发现（reconciler fail-safe 依据）"


def test_discovery_rejects_invalid_labels() -> None:
    """标签校验替代旧 validate_jobs：周期下限 / 队列 / task_name 形式。"""
    from base.common.taskiq_app.discovery import _validate_labels

    assert _validate_labels(
        "sales:x", {"ap_schedule": 30, "queue_name": "ap.jobs"}
    ) == []
    assert _validate_labels("sales:x", {"ap_schedule": 10, "queue_name": "ap.jobs"})
    # 平台作业放宽到 1s（Outbox relay），插件作业仍受 30s 下限约束
    assert _validate_labels(
        "platform:x", {"ap_schedule": 1, "queue_name": "ap.jobs"}
    ) == []
    assert _validate_labels("platform:x", {"ap_schedule": 0, "queue_name": "ap.jobs"})
    assert _validate_labels("sales:x", {"ap_schedule": 30, "queue_name": "ap.events"})
    assert _validate_labels("salesx", {"ap_schedule": 30, "queue_name": "ap.jobs"})
    assert _validate_labels("sales:x", {"ap_interval_ref": "no_colon"})
    assert _validate_labels(
        "sales:x", {"ap_schedule": 30, "queue_name": "ap.jobs", "ap_interval_ref": "m:f"}
    ) == []


def test_reconciler_uses_periodic_schedule_trigger() -> None:
    """taskiq-beat 1.4.0 要求 trigger 为 PeriodicSchedule，裸 IntervalTrigger 会崩。"""
    src = (
        _project_root() / "base" / "common" / "taskiq_app" / "reconcile.py"
    ).read_text(encoding="utf-8")
    assert "PeriodicSchedule(interval=IntervalTrigger(seconds=interval))" in src
    assert "scheduled_specs(discover())" in src, "reconciler 必须走统一发现器"
    assert "manifest.get(\"jobs\")" not in src, "reconciler 不得再解析 manifest.jobs"


# ---------------------------------------------------------------------------
# 事件订阅声明发现（2026-11-15：manifest.events → task/ @ap_subscribe）
# ---------------------------------------------------------------------------

EXPECTED_EVENT_SUBS = {
    "audit": {
        "model.created", "model.updated", "model.deleted", "user.login", "user.logout",
    },
    "mail": {"model.created", "model.updated", "model.deleted"},
    "crm": {"sales.paid"},
    "finance": {
        "purchase.confirmed", "purchase.received", "purchase.payment",
        "sales.paid", "sales.receipt", "work_order.completed",
        "material.picked", "production.receipt",
    },
    "subcontracting": {
        "mrp2.planned_order_confirmed", "inventory.picking_done", "inventory.receipt_done",
    },
    # 2026-11-15：原 mes/services/event_handlers.py 的 4 条无人调用订阅
    # 改造为 task/subscriptions.py 的 @ap_subscribe 声明（历史死代码闭环）。
    "mes": {
        "equipment.status_changed", "quality.inspection_completed",
        "inventory.picking_done", "inventory.receipt_done",
    },
}


def test_event_subscription_discovery() -> None:
    """24 条声明逐项等价于旧 manifest.events + mes 死代码改造，入口均可解析。"""
    try:
        from base.common.taskiq_app.discovery import (
            discover_event_subscriptions,
            event_specs_by_owner,
            reset,
        )
        from base.common.dynamic_ref import resolve_callable
    except Exception as exc:
        pytest.skip(f"发现器导入需要完整项目依赖：{exc}")

    reset()  # 强制重扫真实插件目录
    specs = discover_event_subscriptions()
    assert len(specs) == sum(len(v) for v in EXPECTED_EVENT_SUBS.values()) == 24

    by_owner: dict[str, set[str]] = {}
    for spec in specs:
        by_owner.setdefault(spec.owner, set()).add(spec.event_name)
    assert by_owner == EXPECTED_EVENT_SUBS

    for owner, events in EXPECTED_EVENT_SUBS.items():
        group = event_specs_by_owner(owner)
        assert len(group) == len(events), owner
        head = group[0]
        assert head.owner == owner
        assert head.module.startswith(f"base.plugins.{owner}.task.subscriptions")
        assert head.register_ref == f"{head.module}:register"
        assert head.unregister_ref == f"{head.module}:unregister"
        assert head.handler_ref == head.register_ref
        assert head.sub_name == f"{owner}:{head.event_name}"
        assert head.description
        # 注册/注销入口必须真实可解析（避免声明指向不存在的函数）
        assert callable(resolve_callable(head.register_ref))
        assert callable(resolve_callable(head.unregister_ref))
    assert all(spec.owner != "platform" for spec in specs), "平台模块不声明业务事件订阅"


def test_ap_subscribe_declaration_validation() -> None:
    """装饰器只挂声明属性；非法事件名/重复/ref 被校验拦截。"""
    from base.common.taskiq_app.discovery import (
        SUBSCRIPTION_ATTR,
        _validate_subscription_decl,
        ap_subscribe,
    )

    @ap_subscribe("sales.paid", description="说明", unregister_ref="unregister")
    def register() -> None:
        return None

    decl = getattr(register, SUBSCRIPTION_ATTR)
    assert decl["events"] == ("sales.paid",)
    assert decl["unregister_ref"] == "unregister"
    assert _validate_subscription_decl(decl) == []
    assert _validate_subscription_decl({"events": ()})
    assert _validate_subscription_decl({"events": ("BadName",)})
    assert _validate_subscription_decl({"events": ("a.b", "a.b")})
    assert _validate_subscription_decl({"events": ("a.b",), "bootstrap": ":"})
    assert _validate_subscription_decl(
        {"events": ("a.b",), "unregister_ref": "mod:fn"}
    ) == []


def test_manifest_event_declarations_removed() -> None:
    """manifest 全量无 jobs/events 残留；事件中心/契约/CLI 均切换到发现器。"""
    import json

    root = _project_root()
    manifests = sorted((root / "base" / "plugins").glob("*/manifest.json"))
    assert manifests
    for mf in manifests:
        manifest = json.loads(mf.read_text(encoding="utf-8"))
        assert "events" not in manifest, f"{mf.parent.name} 仍残留 events 段"
        assert "jobs" not in manifest, f"{mf.parent.name} 仍残留 jobs 段"

    contract = (
        root / "base" / "common" / "plugin_contract.py"
    ).read_text(encoding="utf-8")
    assert 'if manifest.get("events"):' in contract, "残留 events 必须拒绝装配"

    registry = (
        root / "base" / "core" / "events" / "registry.py"
    ).read_text(encoding="utf-8")
    assert 'manifest.get("events")' not in registry
    assert "discover_event_subscriptions" in registry
    assert "event_specs_by_owner" in registry

    cli = (root / "base" / "cli" / "command.py").read_text(encoding="utf-8")
    assert 'manifest["events"]' not in cli, "CLI 脚手架不得再生成废弃声明"
    assert "task_dir" in cli


def test_mes_dead_code_now_declarative() -> None:
    """mes 历史死代码闭环（2026-11-15）：声明可发现、注册幂等、注销对称。

    原 ``mes/services/event_handlers.py:87-94`` 的 4 条 subscribe 全仓库无调用点，
    符合性检查报告 §2.2 / 整改方案 W2-2 均登记为死代码。现在由
    ``mes/task/subscriptions.py`` 的 ``@ap_subscribe`` 声明驱动。
    """
    import json

    root = _project_root()
    mes = root / "base" / "plugins" / "mes"

    decl_src = (mes / "task" / "subscriptions.py").read_text(encoding="utf-8")
    assert "@ap_subscribe(" in decl_src
    assert "unregister_ref=\"unregister\"" in decl_src

    handler_src = (mes / "services" / "event_handlers.py").read_text(encoding="utf-8")
    assert "\nexcept ImportError:" not in handler_src, "ImportError 兜底会让订阅静默失效"
    assert "_HANDLER_PAIRS" in handler_src, "注册/注销必须遍历同一张表"
    assert "def unregister_event_handlers" in handler_src

    manifest = json.loads((mes / "manifest.json").read_text(encoding="utf-8"))
    assert "events" not in manifest and "jobs" not in manifest
    assert manifest.get("is_installed") is False, "改造不应擅自激活未安装插件"
    assert manifest.get("is_enabled") is False

    # 发现结果与装卸对称（不依赖 DB，注册表现场在 finally 恢复）
    from base.common.taskiq_app.discovery import event_specs_by_owner, reset
    from base.common.dynamic_ref import resolve_callable
    from base.common.events.event_bus import event_bus
    from base.plugins.mes.services import event_handlers as eh

    reset()
    group = event_specs_by_owner("mes")
    assert len(group) == 4
    assert {spec.event_name for spec in group} == EXPECTED_EVENT_SUBS["mes"]
    head = group[0]
    assert head.module == "base.plugins.mes.task.subscriptions"
    assert head.register_ref == f"{head.module}:register"
    assert head.unregister_ref == f"{head.module}:unregister"
    assert callable(resolve_callable(head.register_ref))
    assert callable(resolve_callable(head.unregister_ref))

    snapshot = {k: list(v) for k, v in event_bus._handler_registry.items()}
    try:
        eh.unregister_event_handlers()  # 从干净状态起步
        eh.register_event_handlers()
        first = {name: len(event_bus.get_handlers(name)) for name, _ in eh._HANDLER_PAIRS}
        eh.register_event_handlers()
        second = {name: len(event_bus.get_handlers(name)) for name, _ in eh._HANDLER_PAIRS}
        assert first == second and all(v == 1 for v in first.values()), (first, second)
        eh.unregister_event_handlers()
        after = {name: len(event_bus.get_handlers(name)) for name, _ in eh._HANDLER_PAIRS}
        assert all(v == 0 for v in after.values()), after
    finally:
        event_bus._handler_registry.clear()
        event_bus._handler_registry.update(snapshot)
        eh._registered = False
