"""事件中心管理服务：订阅 CRUD、发布记录查询与重放、详情、统计。"""
from __future__ import annotations

import json
from typing import Any

from tortoise.functions import Count

from base.common.events.models.event_record import EventRecord
from base.common.events.payload_contract import sanitize_json, sanitize_text
from base.common.plugin_symbol import PluginSymbolUnavailable, resolve_plugin_symbol
from base.core.events import contract
from base.core.events.models import EventSubscription
from base.core.events.registry import event_center

# 审计模型属于插件层，core 不静态 import：统一经 plugin_symbol 解析器惰性获取，
# 插件未安装/表未建立时详情接口降级为「无关联记录」而不是 500。
_TRACE_MODEL_PATHS = {
    "audit_logs": "base.plugins.audit.models.audit_log.AuditLog",
    "request": "base.plugins.audit.models.audit_log.InputLayerLog",
    "response": "base.plugins.audit.models.audit_log.OutputLayerLog",
    "executions": "base.plugins.audit.models.audit_log.ExecutionLayerLog",
}
TRACE_LOG_LIMIT = 5
TRACE_EXECUTION_LIMIT = 20


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


async def _trace_rows(section: str, trace_id: str, limit: int) -> list:
    try:
        model = resolve_plugin_symbol(_TRACE_MODEL_PATHS[section])
    except PluginSymbolUnavailable as exc:
        raise LookupError(str(exc)) from exc
    return await model.filter(trace_id=trace_id).order_by("-created_at").limit(limit)


async def load_trace_context(trace_id: str | None) -> dict:
    """按 trace_id 回查原始 HTTP 请求与响应（审计插件，可选能力）。

    数据源分工：AuditLog 记 method/path/status/duration；InputLayerLog.context_data
    记请求体 + query；OutputLayerLog.final_output 记响应正文；ExecutionLayerLog 记
    链路中各步的参数与返回值。所有字段在返回前统一脱敏 + 限长。
    """
    result: dict = {
        "trace_id": trace_id,
        "available": False,
        "reason": None,
        "audit_logs": [],
        "request": None,
        "response": None,
        "executions": [],
        "errors": [],
    }
    if not trace_id:
        result["reason"] = "该事件未关联 trace_id（非 HTTP 请求触发，或审计中间件未覆盖该路径）"
        return result

    for section, limit in (
        ("audit_logs", TRACE_LOG_LIMIT),
        ("request", 1),
        ("response", 1),
        ("executions", TRACE_EXECUTION_LIMIT),
    ):
        try:
            rows = await _trace_rows(section, trace_id, limit)
        except Exception as exc:
            result["errors"].append(f"{section}: {exc}"[:300])
            continue
        if section == "audit_logs":
            result[section] = [
                {
                    "operation": getattr(r, "operation", None),
                    "method": getattr(r, "method", None),
                    "path": getattr(r, "path", None),
                    "status_code": getattr(r, "status_code", None),
                    "duration": getattr(r, "duration", None),
                    "level": getattr(r, "level", None),
                    "ip_address": getattr(r, "ip_address", None),
                    "request_params": sanitize_json(getattr(r, "request_params", None)),
                    "response_data": sanitize_text(getattr(r, "response_data", None)),
                    "error_message": sanitize_text(getattr(r, "error_message", None)),
                    "created_at": _iso(getattr(r, "created_at", None)),
                }
                for r in rows
            ]
        elif section == "request":
            result[section] = (
                {
                    "user_instruction": sanitize_text(getattr(rows[0], "user_instruction", None)),
                    "context_data": sanitize_json(getattr(rows[0], "context_data", None)),
                    "created_at": _iso(getattr(rows[0], "created_at", None)),
                }
                if rows else None
            )
        elif section == "response":
            result[section] = (
                {
                    "final_output": sanitize_text(getattr(rows[0], "final_output", None)),
                    "format_compliance": getattr(rows[0], "format_compliance", None),
                    "created_at": _iso(getattr(rows[0], "created_at", None)),
                }
                if rows else None
            )
        else:
            result[section] = [
                {
                    "execution_type": getattr(r, "execution_type", None),
                    "target_name": getattr(r, "target_name", None),
                    "parameters": sanitize_json(getattr(r, "parameters", None)),
                    "return_value": sanitize_json(getattr(r, "return_value", None)),
                    "status": getattr(r, "status", None),
                    "error_message": sanitize_text(getattr(r, "error_message", None)),
                    "duration": getattr(r, "duration", None),
                }
                for r in rows
            ]

    result["available"] = any(
        result[k] for k in ("audit_logs", "request", "response", "executions")
    )
    if not result["available"] and not result["errors"]:
        result["reason"] = "审计模块中未找到该 trace_id 的记录（可能已被清理或未启用）"
    elif result["errors"]:
        result["reason"] = "部分审计数据不可用，详见 errors"
    return result


class EventCenterService:
    @staticmethod
    async def list_subscriptions(
        event_name: str | None = None,
        subscriber: str | None = None,
        source: str | None = None,
    ) -> list[dict]:
        qs = EventSubscription.all()
        if event_name:
            qs = qs.filter(event_name__icontains=event_name)
        if subscriber:
            qs = qs.filter(subscriber__icontains=subscriber)
        if source:
            qs = qs.filter(source=source)
        subs = await qs.order_by("subscriber", "event_name")
        return [await sub.to_dict() for sub in subs]

    @staticmethod
    async def create_subscription(data: dict) -> EventSubscription:
        name = (data.get("name") or "").strip()
        event_name = (data.get("event_name") or "").strip()
        handler_ref = (data.get("handler_ref") or "").strip() or None
        problems = contract.validate_subscription(event_name, handler_ref)
        if not name:
            problems.append("name 不能为空")
        if problems:
            raise ValueError("; ".join(problems))
        if await EventSubscription.filter(name=name).exists():
            raise ValueError(f"订阅名称已存在: {name}")
        if handler_ref:
            from base.core.events.registry import resolve_callable

            try:
                resolve_callable(handler_ref)
            except Exception as e:
                raise ValueError(f"handler_ref 无法解析: {e}")

        sub = await EventSubscription.create(
            name=name,
            event_name=event_name,
            subscriber=(data.get("subscriber") or "custom").strip(),
            handler_ref=handler_ref,
            source="manual",
            is_enabled=bool(data.get("is_enabled", True)),
            is_system=False,
            max_retries=int(data.get("max_retries") or contract.DEFAULT_MAX_RETRIES),
            timeout_ms=int(data.get("timeout_ms") or contract.DEFAULT_TIMEOUT_MS),
            description=data.get("description"),
            extra=data.get("extra") or {},
        )
        if sub.is_enabled and handler_ref:
            await event_center.bind_manual(sub)
        return sub

    @staticmethod
    async def update_subscription(sub: EventSubscription, data: dict) -> EventSubscription:
        allowed = {"description", "max_retries", "timeout_ms", "handler_ref", "is_enabled", "extra"}
        updates = {k: v for k, v in data.items() if k in allowed and v is not None}
        if "handler_ref" in updates:
            problems = contract.validate_subscription(sub.event_name, updates["handler_ref"])
            if problems:
                raise ValueError("; ".join(problems))
            # handler 变化时重新绑定
            await event_center.unbind_manual(sub.name, sub.event_name)
            need_rebind = True
        else:
            need_rebind = False
        if updates:
            await EventSubscription.filter(id=sub.id).update(**updates)
        refreshed = await EventSubscription.get(id=sub.id)
        if "is_enabled" in updates:
            await event_center.set_enabled(refreshed, bool(updates["is_enabled"]))
        if need_rebind and refreshed.is_enabled:
            await event_center.bind_manual(refreshed)
        return refreshed

    @staticmethod
    async def delete_subscription(sub: EventSubscription) -> None:
        if sub.is_system:
            raise ValueError("系统声明订阅不可删除，请在插件 manifest 或插件启停中管理")
        await event_center.unbind_manual(sub.name, sub.event_name)
        await sub.delete()

    @staticmethod
    async def list_records(
        event_name: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        qs = EventRecord.all()
        if event_name:
            qs = qs.filter(event_name__icontains=event_name)
        if status:
            qs = qs.filter(status=status)
        total = await qs.count()
        rows = await qs.order_by("-published_at").offset((page - 1) * page_size).limit(page_size)
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [await row.to_dict() for row in rows],
        }

    @staticmethod
    async def get_record_detail(event_uuid: str) -> dict | None:
        """后台事件详情：Outbox 记录全文 + Inbox 每个 handler 的执行结果。

        ``EventRecord.payload`` 已在发布端脱敏（业务直调也走 sanitize_payload）；
        ``EventInbox.return_value`` 由 worker 收集并脱敏后写入。历史行没有该列
        数据时返回明确的说明对象，而不是让前端显示一个含糊的 '-'。
        ``trace`` 按 ``trace_id`` 回查审计插件里的原始 HTTP 请求与响应。
        """
        from base.common.events.models.event_inbox import EventInbox

        record = await EventRecord.get_or_none(event_uuid=event_uuid)
        if not record:
            return None

        handlers: list[dict] = []
        rows = await EventInbox.filter(event_uuid=event_uuid).order_by("handler_key")
        for row in rows:
            rv = row.return_value
            if isinstance(rv, str):
                try:
                    rv = json.loads(rv)
                except (TypeError, ValueError):
                    rv = {"value": rv}
            if rv is None:
                # 不再让后台出现语义不明的 '-'：区分「无返回值 / 失败 / 历史行 / 未完成」
                if row.status == "done":
                    rv = {
                        "__no_return__": True,
                        "note": "handler 未返回值" if getattr(row, "execution_time_ms", None) is not None
                        else "该记录早于返回值采集上线，无历史返回值",
                    }
                elif row.status == "failed":
                    rv = {"__failed__": True, "note": "handler 执行失败，无返回值"}
                else:
                    rv = {"__pending__": True, "note": "handler 尚未完成"}
            handlers.append({
                "handler_key": row.handler_key,
                "status": row.status,
                "attempts": row.attempts,
                "error_message": row.error_message,
                "error_detail": getattr(row, "error_detail", None),
                "execution_time_ms": getattr(row, "execution_time_ms", None),
                "return_value": rv,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            })

        record_dict = await record.to_dict()
        return {
            "record": record_dict,
            "handlers": handlers,
            "trace": await load_trace_context(record.trace_id),
        }

    @staticmethod
    async def replay(event_uuid: str, reason: str = "") -> dict:
        """重放 = 同一 event_uuid 置回 pending，交给 outbox relay 重新投递。

        不再直接 kiq：投递只有 relay 一条通道，状态修改与审计同事务，
        且复用原 event_uuid（消费端 Inbox 幂等键保持不变）。
        """
        from datetime import datetime, timezone

        from tortoise.transactions import in_transaction

        record = await EventRecord.get_or_none(event_uuid=event_uuid)
        if not record:
            raise ValueError("事件记录不存在")
        if record.status not in ("failed", "dead_letter"):
            raise ValueError(f"仅 failed/dead_letter 可重放，当前状态 {record.status}")
        if not record.payload:
            raise ValueError("事件载荷为空，无法重放")

        async with in_transaction():
            updated = await EventRecord.filter(
                event_uuid=event_uuid, status__in=("failed", "dead_letter")
            ).update(
                status="pending",
                retry_count=0,
                dispatch_attempts=0,
                locked_until=None,
                dispatched_at=None,
                replay_count=(record.replay_count or 0) + 1,
                error_message=None,
                published_at=datetime.now(timezone.utc),
            )
            if not updated:
                raise ValueError("事件状态已被其它操作变更，请重试")

        return {
            "event_uuid": event_uuid,
            "replayed": True,
            "status": "pending",
            "reason": reason,
        }

    @staticmethod
    async def stats() -> dict:
        subs = await EventSubscription.all()
        by_source: dict[str, int] = {}
        by_event: dict[str, int] = {}
        enabled = 0
        for sub in subs:
            by_source[sub.source] = by_source.get(sub.source, 0) + 1
            by_event[sub.event_name] = by_event.get(sub.event_name, 0) + 1
            enabled += 1 if sub.is_enabled else 0
        status_rows = (
            await EventRecord.all().group_by("status").annotate(count=Count("id")).values("status", "count")
        )
        return {
            "subscriptions": len(subs),
            "enabled_subscriptions": enabled,
            "by_source": by_source,
            "by_event": by_event,
            "records_by_status": {row["status"]: row["count"] for row in status_rows},
        }
