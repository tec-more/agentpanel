"""事件中心管理服务：订阅 CRUD、发布记录查询与重放、统计。"""
from __future__ import annotations

import json
from typing import Any

from tortoise.functions import Count

from base.common.events.event_bus import event_bus
from base.common.events.models.event_record import EventRecord
from base.core.events import contract
from base.core.events.models import EventSubscription
from base.core.events.registry import event_center


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
    async def replay(event_uuid: str, reason: str = "") -> dict:
        record = await EventRecord.get_or_none(event_uuid=event_uuid)
        if not record:
            raise ValueError("事件记录不存在")
        if record.status not in ("failed", "dead_letter"):
            raise ValueError(f"仅 failed/dead_letter 可重放，当前状态 {record.status}")
        payload = record.payload
        if isinstance(payload, str):
            payload = json.loads(payload)
        payload = dict(payload or {})
        payload.pop("idempotency_key", None)
        await event_bus.publish(record.event_name, **payload)
        await EventRecord.filter(id=record.id).update(
            status="published",
            replay_count=(record.replay_count or 0) + 1,
        )
        return {"event_uuid": event_uuid, "replayed": True, "reason": reason}

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
