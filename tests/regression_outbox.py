"""Transactional Outbox / Inbox 事务一致性回归（2026-11-15）。

覆盖：表结构与迁移、发布端只落库、投递唯一通道、relay 租约 CAS、
两阶段消费事务、Inbox 已完成 handler 跳过、状态机 CAS、重放回 pending、
平台作业声明与周期下限放宽。全部为纯单测，不依赖 RabbitMQ / PG 实例。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_outbox_models_and_migrations() -> None:
    from base.common.database import parse_migration_filename
    from base.common.events.models.event_inbox import EventInbox
    from base.common.events.models.event_record import EventRecord
    from base.common.setting import TORTOISE_ORM

    fields = set(EventRecord._meta.fields_map)
    assert {
        "idempotency_key", "dispatch_attempts", "locked_until",
        "dispatched_at", "consuming_started_at", "trace_id",
    } <= fields, "Outbox 字段缺失"
    assert EventRecord._meta.fields_map["idempotency_key"].unique is True
    assert EventInbox._meta.fields_map["dedup_key"].unique is True
    assert {
        "return_value", "execution_time_ms", "error_detail",
    } <= set(EventInbox._meta.fields_map), "Inbox 需记录 handler 返回值与执行摘要"
    assert "base.common.events.models.event_inbox" in (
        TORTOISE_ORM["apps"]["models"]["models"]
    )

    alter = list((ROOT / "migrations").glob("core_alter_table_event_records_*.sql"))
    inbox = list((ROOT / "migrations").glob("core_create_table_event_inbox_*.sql"))
    inbox_alter = list((ROOT / "migrations").glob("core_alter_table_event_inbox_*.sql"))
    assert len(alter) == 1 and len(inbox) == 1 and len(inbox_alter) == 1
    alter_sql = alter[0].read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_event_records_idempotency_key" in alter_sql
    assert "ADD COLUMN IF NOT EXISTS consuming_started_at" in alter_sql
    assert "ADD COLUMN IF NOT EXISTS trace_id VARCHAR(100)" in alter_sql
    assert "idx_event_records_trace_id" in alter_sql
    inbox_create_sql = inbox[0].read_text(encoding="utf-8")
    assert "dedup_key VARCHAR(300) NOT NULL UNIQUE" in inbox_create_sql
    assert "return_value JSONB" in inbox_create_sql, "全新库须直接建出该列"
    assert "error_detail TEXT" in inbox_create_sql and "execution_time_ms INT" in inbox_create_sql
    inbox_alter_sql = inbox_alter[0].read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS return_value JSONB" in inbox_alter_sql, "已有库须能幂等补列"
    assert "ADD COLUMN IF NOT EXISTS error_detail TEXT" in inbox_alter_sql
    assert "ADD COLUMN IF NOT EXISTS execution_time_ms INT" in inbox_alter_sql
    # 目标库是 openGauss（非原生 PostgreSQL），没有 to_regclass()：
    # 迁移必须用 information_schema 判表 + EXECUTE 动态 DDL，否则整批迁移中断。
    assert "information_schema.tables" in inbox_alter_sql
    assert "EXECUTE 'ALTER TABLE event_inbox" in inbox_alter_sql
    for f in (ROOT / "migrations").glob("core_*.sql"):
        body = "\n".join(line.split("--")[0] for line in f.read_text(encoding="utf-8").splitlines())
        assert "to_regclass(" not in body, f"{f.name}: openGauss 不支持 to_regclass()"
    for f in alter + inbox + inbox_alter:
        assert parse_migration_filename(f.name) is not None, f.name


def test_publish_writes_only_db(monkeypatch) -> None:
    """发布成功 = 事务内写 pending 记录；唯一键冲突 = duplicate，不抛给业务。"""
    from tortoise.exceptions import IntegrityError
    import tortoise.transactions as txn

    import base.common.events.models.event_record as er_mod
    from base.common.events.event_bus_adapter import EventBusAdapter

    calls: list[dict] = []
    fail_next = {"value": False}

    class _FakeCM:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            return False

    class _FakeRecord:
        @staticmethod
        async def create(**kwargs):
            calls.append(kwargs)
            if fail_next["value"]:
                raise IntegrityError("duplicate key")

    monkeypatch.setattr(er_mod, "EventRecord", _FakeRecord)
    monkeypatch.setattr(txn, "in_transaction", lambda: _FakeCM())

    ok = asyncio.run(
        EventBusAdapter().publish("t.created", idempotency_key="k1", x=1, _source_module="test")
    )
    assert ok["published"] is True and ok["status"] == "pending"
    assert ok["event_uuid"]
    assert calls[0]["status"] == "pending"
    assert calls[0]["idempotency_key"] == "k1"
    assert calls[0]["source_module"] == "test"
    assert calls[0]["payload"] == {"x": 1}, "控制字段不得混进业务载荷"

    fail_next["value"] = True
    dup = asyncio.run(EventBusAdapter().publish("t.created", idempotency_key="k1"))
    assert dup["published"] is False and dup["duplicate"] is True
    assert dup["event_uuid"] is None


def test_audit_probe_excludes_outbox_tables() -> None:
    """消息表不得被 ORM 审计探针捕获，否则每条消息都会派生新事件（无限风暴）。"""
    src = _read("base/plugins/audit/services/orm_event_service.py")
    exclude_block = src.split("AUDIT_EXCLUDE_MODELS = [", 1)[1].split("]", 1)[0]
    for name in ("EventRecord", "EventInbox", "ReplayAuditLog"):
        assert f"'{name}'" in exclude_block, f"{name} 未排除"


def test_relay_is_the_only_dispatch_producer() -> None:
    """全仓 base/ 下只有 outbox.py 能 dispatch.kiq —— 投递唯一通道。"""
    producers = sorted(
        p.name
        for p in (ROOT / "base").rglob("*.py")
        if "dispatch.kiq(" in p.read_text(encoding="utf-8", errors="ignore")
    )
    assert producers == ["outbox.py"], f"存在旁路投递: {producers}"


def test_relay_uses_cas_lease_and_published_transition() -> None:
    src = _read("base/common/taskiq_app/outbox.py")
    assert 'Q(status="pending")' in src, "relay 必须扫 pending"
    assert 'Q(status="failed", next_retry_at__lte=now)' in src, "failed 退避到期须纳入补投"
    assert "locked_until=lease_until" in src, "多副本需租约抢占"
    assert "EventRecordService.transition(" in src, "状态修改必须走 CAS"
    assert 'from_states=(row.status,)' in src, "pending/failed 分别 CAS，互不覆盖"
    assert 'status="published"' in src
    assert "_release_lease" in src and "保持原状态" in src, "投递失败须留在 outbox"
    assert "reap_stale_consuming" in src and "consuming_started_at__lt" in src
    assert "reap_stale_published" in src, "投递无 confirm，需回收未确认 published"


def test_dispatch_two_phase_transaction_and_inbox() -> None:
    src = _read("base/common/taskiq_app/events.py")
    assert src.count("async with in_transaction():") == 2, "必须是两段事务，handler 在事务外"
    open_tx = src.find("async with in_transaction():")
    handler_call = src.find("= handler(msg.event_name, **msg.payload)")
    close_tx = src.find("async with in_transaction():", open_tx + 1)
    assert open_tx < handler_call < close_tx, "handler 执行不得包在 DB 事务里"
    assert 'row.status == "done"' in src, "Inbox 已成功的 handler 必须跳过"
    assert "EventInbox.create(" in src and "finished_at=finished_at" in src
    assert "EventRecordService.transition(" in src
    assert "raise RuntimeError" not in src, "失败不得上抛（会触发断掉的 delay 重投）"
    assert "retry_on_error=False" in src, "dispatch 必须显式禁用中间件重投"
    assert "next_retry_at_for(retry_count, finished_at)" in src, "退避时间须落库供 relay 补投"
    assert "execution_time_ms=exec_ms" in src and "error_detail=detail" in src


def test_concurrent_duplicate_delivery_is_rejected() -> None:
    """CAS 允许集刻意不含 consuming，防止并发重复投递双执行。"""
    from base.common.taskiq_app.events import _ACTIVE_STATES, _TERMINAL_STATUSES

    assert "consuming" not in _ACTIVE_STATES
    assert "pending" in _ACTIVE_STATES and "failed" in _ACTIVE_STATES
    assert _TERMINAL_STATUSES == frozenset({"consumed", "dead_letter"})


def test_state_transition_is_cas_with_whitelist() -> None:
    src = _read("base/common/events/services/event_record_service.py")
    assert "status__in=list(from_states)" in src
    assert "_TRANSITION_FIELDS" in src
    assert "async def transition(" in src


def test_replay_paths_both_reset_to_pending() -> None:
    for rel in (
        "base/core/events/service.py",
        "base/common/events/services/event_replay_service.py",
    ):
        src = _read(rel)
        assert 'status="pending"' in src, rel
        assert 'status__in=("failed", "dead_letter")' in src, rel
        assert "dispatch.kiq" not in src, f"{rel} 不得绕过 relay 直投"
        assert "in_transaction()" in src, rel


def test_platform_outbox_jobs_declared() -> None:
    from base.common.plugin_contract import MIN_JOB_INTERVAL
    from base.common.taskiq_app.discovery import (
        PLATFORM_MIN_JOB_INTERVAL,
        discover,
        scheduled_specs,
    )

    assert MIN_JOB_INTERVAL == 30 and PLATFORM_MIN_JOB_INTERVAL == 1
    by_name = {spec.task_name: spec for spec in scheduled_specs(discover())}
    assert by_name["platform:outbox_relay"].schedule == 1
    assert by_name["platform:stale_consuming_reap"].schedule == 30
    assert len(by_name) == 8


# ---------------------------------------------------------------------------
# 后台观测能力（2026-11-15 追加）：载荷脱敏 + handler 返回值 + 详情接口
# ---------------------------------------------------------------------------


def test_payload_contract_single_source_and_layer_direction() -> None:
    """规则常量下沉到 common；core 只做再导出，不出现第二套阈值。"""
    from base.common.events import payload_contract as pc
    from base.core.events import contract

    assert contract.validate_payload is pc.validate_payload
    assert contract.MAX_PAYLOAD_BYTES == pc.MAX_PAYLOAD_BYTES
    assert contract.FORBIDDEN_PAYLOAD_KEYS == pc.FORBIDDEN_PAYLOAD_KEYS
    assert sorted(contract.RULES["payload"]["forbidden_keys"]) == sorted(
        pc.FORBIDDEN_PAYLOAD_KEYS
    )
    assert "base.core.events" not in _read(
        "base/common/events/event_bus_adapter.py"
    ), "base/common 不得反向依赖 base/core"
    assert contract.validate_payload({"x": 1}) == []
    assert contract.validate_payload({"token": "abc"}), "后台手动发布仍严格拒绝凭据字段"
    assert contract.validate_payload([]), "非 dict 载荷必须拒绝"


def test_business_publish_is_masked_not_rejected(monkeypatch) -> None:
    """业务直调含凭据字段：遮蔽而非抛错，不打断 @atomic() 业务事务。"""
    import tortoise.transactions as txn

    import base.common.events.models.event_record as er_mod
    from base.common.events.event_bus_adapter import EventBusAdapter

    calls: list[dict] = []

    class _FakeCM:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            return False

    class _FakeRecord:
        @staticmethod
        async def create(**kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(er_mod, "EventRecord", _FakeRecord)
    monkeypatch.setattr(txn, "in_transaction", lambda: _FakeCM())

    ok = asyncio.run(
        EventBusAdapter().publish(
            "sales.paid",
            order_id=7,
            token="plain-secret",
            nested={"api_key": "k", "ok": 1},
        )
    )
    assert ok["published"] is True, "脱敏路径不得抛异常回滚业务事务"
    saved = calls[0]["payload"]
    assert saved["order_id"] == 7
    assert saved["token"] == "***"
    assert saved["nested"]["api_key"] == "***"
    assert saved["nested"]["ok"] == 1, "非敏感字段必须原样保留"


def test_payload_and_result_size_guards() -> None:
    from base.common.events.payload_contract import (
        MAX_PAYLOAD_BYTES,
        MAX_RESULT_BYTES,
        sanitize_payload,
        to_jsonable,
    )

    big = sanitize_payload({"blob": "x" * (MAX_PAYLOAD_BYTES + 100)})
    assert big["__truncated__"] is True and big["size_bytes"] > MAX_PAYLOAD_BYTES
    assert len(big["preview"]) <= 512

    assert to_jsonable(None) is None
    got = to_jsonable({"order_id": 1, "token": "abc", "nested": {"private_key": "k"}})
    assert got["token"] == "***" and got["nested"]["private_key"] == "***"
    assert got["order_id"] == 1
    huge = to_jsonable({"blob": "x" * (MAX_RESULT_BYTES + 100)})
    assert huge["__truncated__"] is True and len(huge["preview"]) <= 512


def test_dispatch_collects_handler_return_value() -> None:
    src = _read("base/common/taskiq_app/events.py")
    assert "to_jsonable(returned)" in src, "必须捕获 handler 返回值"
    assert "return_value=returned_json" in src, "事务②必须写回 Inbox"
    assert "if asyncio.iscoroutine(returned):" in src
    assert "await asyncio.wait_for(" in src, "异步 handler 的返回值也要收集"


def test_event_detail_api_exposes_payload_and_inbox() -> None:
    svc = _read("base/core/events/service.py")
    api = _read("base/core/events/api/v1/event_center.py")
    js = _read("web/src/api/eventCenter.js")
    vue = _read("web/src/views/events/Index.vue")

    assert "async def get_record_detail(" in svc
    assert "EventInbox.filter(event_uuid=event_uuid)" in svc
    assert '"return_value": rv' in svc and '"record": record_dict' in svc
    assert "await load_trace_context(record.trace_id)" in svc, "详情须按 trace_id 串联审计"
    assert '/records/{event_uuid}/detail' in api
    assert "require_admin" in api.split("/records/{event_uuid}/detail")[1][:400]
    assert "getRecordDetail" in js and "getRecordDetail" in vue
    assert "<el-drawer" in vue and "handleDetail" in vue
    assert "formatJson(detailData.record?.payload)" in vue, "抽屉须展示请求载荷"
    assert "row.return_value" in vue, "抽屉须展示每个 handler 的返回值"


# ---------------------------------------------------------------------------
# 2026-11-15 第二轮：trace_id 串联 / 执行摘要 / DB 状态机重试
# ---------------------------------------------------------------------------


def test_publish_inherits_trace_id_from_request_context(monkeypatch) -> None:
    """HTTP 请求内发布的事件继承 trace_id；控制字段不得混进 payload。"""
    import tortoise.transactions as txn

    import base.common.events.models.event_record as er_mod
    import base.common.events.event_bus_adapter as adapter_mod

    calls: list[dict] = []

    class _FakeCM:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *args):
            return False

    class _FakeRecord:
        @staticmethod
        async def create(**kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(er_mod, "EventRecord", _FakeRecord)
    monkeypatch.setattr(txn, "in_transaction", lambda: _FakeCM())
    monkeypatch.setattr(adapter_mod, "get_current_trace_id", lambda: "trace-http-001")

    asyncio.run(adapter_mod.EventBusAdapter().publish("sales.paid", order_id=9))
    assert calls[0]["trace_id"] == "trace-http-001"
    assert calls[0]["payload"] == {"order_id": 9}

    # 显式传入的控制字段优先，且不进入载荷
    asyncio.run(
        adapter_mod.EventBusAdapter().publish(
            "job.tick", _trace_id="job-trace-002", x=1
        )
    )
    assert calls[1]["trace_id"] == "job-trace-002"
    assert calls[1]["payload"] == {"x": 1}


def test_trace_context_uses_plugin_symbol_and_masks_credentials() -> None:
    """core 不静态 import 插件模型；审计文本统一脱敏。"""
    from base.common.events.payload_contract import sanitize_text
    from base.core.events.service import _TRACE_MODEL_PATHS, load_trace_context

    svc = _read("base/core/events/service.py")
    assert "resolve_plugin_symbol" in svc and "base.plugins.audit.models.audit_log" in svc
    assert "from base.plugins" not in svc, "core 不得静态 import 插件模型"
    assert set(_TRACE_MODEL_PATHS) == {"audit_logs", "request", "response", "executions"}

    masked = sanitize_text('{"token": "abc123", "password": "p@ss"}')
    assert "abc123" not in masked and "p@ss" not in masked

    # 无 trace_id 时返回明确原因，不抛异常、不查库
    empty = asyncio.run(load_trace_context(None))
    assert empty["available"] is False and empty["reason"]


def test_detail_marks_missing_return_value_explicitly() -> None:
    """历史行 / 无返回值 / 失败 / 未完成都有说明对象，后台不再显示裸 '-'。"""
    svc = _read("base/core/events/service.py")
    for marker in ("__no_return__", "__failed__", "__pending__"):
        assert marker in svc, f"缺少 {marker} 说明"
    src = _read("base/common/taskiq_app/events.py")
    assert "_NO_RETURN_MARKER" in src and "dict(_NO_RETURN_MARKER)" in src
    assert "_error_detail" in src and "traceback.format_exception" in src


def test_retry_backoff_and_db_driven_redelivery() -> None:
    """退避 5/10/20/40... 封顶 300s；relay 是 failed 唯一补投通道。"""
    from datetime import datetime, timezone

    from base.common.taskiq_app import outbox

    delays = [outbox.next_retry_delay(n) for n in (1, 2, 3, 4, 99)]
    assert delays == [5, 10, 20, 40, 300], delays
    now = datetime(2026, 11, 15, tzinfo=timezone.utc)
    assert outbox.next_retry_at_for(1, now) == now.replace(second=5)

    src = _read("base/common/taskiq_app/outbox.py")
    assert "MAX_UNCONFIRMED_ATTEMPTS" in src and "STALE_PUBLISHED_SECONDS" in src
    assert '"retried"' in src, "重投计数须可观测"
    platform = _read("base/common/taskiq_app/platform_jobs.py")
    assert "reap_stale_published" in platform
    assert "retried=" in platform


def test_broker_disables_delay_retry_and_validates_ack_type() -> None:
    from base.common.taskiq_app.broker import broker
    from taskiq.middlewares.smart_retry_middleware import SmartRetryMiddleware

    retries = [m for m in broker.middlewares if isinstance(m, SmartRetryMiddleware)]
    assert retries and retries[0].default_retry_label is False

    from base.common.taskiq_app.config import settings
    from taskiq.acks import parse_acknowledge_type

    assert parse_acknowledge_type(settings.ack_type).value == "when_executed"
    src = _read("base/common/taskiq_app/broker.py")
    assert "parse_acknowledge_type(settings.ack_type)" in src
    assert "default_retry_label=False" in src


def test_frontend_shows_trace_and_execution_summary() -> None:
    vue = _read("web/src/views/events/Index.vue")
    assert "关联 HTTP 请求 / 响应" in vue
    assert "detailData.trace.audit_logs" in vue
    assert "detailData.trace.request?.context_data" in vue
    assert "detailData.trace.response?.final_output" in vue
    assert "row.execution_time_ms" in vue
    assert "row.error_detail" in vue
    assert "detailData.record?.trace_id" in vue
