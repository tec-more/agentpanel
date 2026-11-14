"""事件注册表：订阅/发布的统一入口。

- 插件订阅来自 manifest.events（声明式），随插件启用/禁用同步注册与注销；
- 后台新增的 manual 订阅按 handler_ref 动态绑定，支持单条即时启停；
- 发布统一经 EventCenter.publish 校验规则 → EventBusAdapter.publish 入队
  ``ap.events``（M3：不在本进程执行订阅者，执行全部在 taskiq worker）；
- 发布端幂等去重迁移 Redis（D6：多 API worker 跨进程生效；
  Redis 不可用时回退进程内 dict，语义同旧实现）。
"""
from __future__ import annotations

import inspect
import time
from typing import Any, Callable

from loguru import logger

# W2-3：解析器下沉到 base/common，供事件中心与作业调度器共用。
# 这里保留同名再导出，既有 `from base.core.events.registry import resolve_callable`
# 的调用方不受影响。
from base.common.dynamic_ref import resolve_callable  # noqa: F401
from base.common.events.event_bus import event_bus
from base.core.events import contract
from base.core.events.models import EventSubscription

IDEMPOTENCY_TTL = 300


class EventCenter:
    def __init__(self) -> None:
        self._bound_plugins: set[str] = set()
        self._bootstrapped: set[str] = set()
        self._wrapped: dict[str, Callable] = {}
        self._idempotency: dict[str, float] = {}

    # ---------- 规则 ----------

    @staticmethod
    def rules() -> dict[str, Any]:
        return contract.RULES

    # ---------- 声明式订阅同步 ----------

    async def initialize(self) -> None:
        """在 init_data() 之后调用：同步已启用插件声明并绑定后台自定义订阅。

        app 进程调用 → 填充生产探针 + 订阅注册表；taskiq worker 进程同样调用
        （worker 的 dispatch 任务按进程内注册表取 handler 执行，见
        base/common/taskiq_app/events.py §消费模型）。
        """
        try:
            from base.common.plugin_gate import active_plugin_names
            from base.common.plugin_manager import get_plugin_manager

            manager = get_plugin_manager()
            for name in active_plugin_names():
                manifest = manager.get_manifest(name) or {}
                await self.sync_plugin(name, manifest, active=True)
        except Exception as e:
            logger.error(f"[事件中心] 同步插件声明失败: {e}")
        await self.bind_manual_subscriptions()

    async def resync(self) -> None:
        """周期重扫（worker 长驻进程调用，与 beat reconciler 语义对齐）。

        API 进程的插件启停只改本进程注册表；worker 需靠周期 resync 收敛：
        - 新启用插件 → sync_plugin(active=True)（幂等，register_ref 只执行一次）
        - 已停用插件 → sync_plugin(active=False)（unregister_ref 摘除注册表）
        manual 订阅的启停由 guarded 包装器按 DB 状态即时生效，无需重扫。
        """
        try:
            from base.common.plugin_gate import active_plugin_names
            from base.common.plugin_manager import get_plugin_manager

            manager = get_plugin_manager()
            active = set(active_plugin_names())
            for name in list(self._bound_plugins):
                if name not in active:
                    await self.sync_plugin(
                        name, manager.get_manifest(name) or {}, active=False
                    )
            for name in sorted(active):
                await self.sync_plugin(name, manager.get_manifest(name) or {}, active=True)
        except Exception as e:
            logger.warning(f"[事件中心] resync 失败(下一轮重试): {e}")

    async def sync_plugin(self, name: str, manifest: dict, active: bool) -> None:
        """插件启用/禁用时由 plugin_manager 调用：装卸对称、可重复执行。"""
        events = manifest.get("events") or {}
        if not isinstance(events, dict):
            return

        try:
            bootstrap = events.get("bootstrap")
            if active and bootstrap and name not in self._bootstrapped:
                await self._invoke(bootstrap)
                self._bootstrapped.add(name)

            for item in events.get("subscribe") or []:
                event_name = item.get("event_name") if isinstance(item, dict) else str(item)
                handler_ref = item.get("handler_ref") if isinstance(item, dict) else None
                problems = contract.validate_event_name(event_name)
                if problems:
                    logger.warning(f"[事件中心] 插件 {name} 声明被忽略: {problems}")
                    continue
                sub_name = f"{name}:{event_name}"
                defaults = {
                    "event_name": event_name,
                    "subscriber": name,
                    "handler_ref": handler_ref,
                    "source": "declared",
                    "is_enabled": active,
                    "is_system": True,
                    "description": (item.get("description") if isinstance(item, dict) else None),
                }
                sub = await EventSubscription.filter(name=sub_name).first()
                if sub:
                    await EventSubscription.filter(id=sub.id).update(
                        event_name=event_name,
                        subscriber=name,
                        handler_ref=handler_ref,
                        source="declared",
                        is_enabled=active,
                        is_system=True,
                    )
                else:
                    await EventSubscription.create(name=sub_name, **defaults)

            if active:
                register_ref = events.get("register_ref")
                if register_ref and name not in self._bound_plugins:
                    await self._invoke(register_ref)
                    self._bound_plugins.add(name)
            else:
                unregister_ref = events.get("unregister_ref")
                if unregister_ref:
                    await self._invoke(unregister_ref)
                    self._bound_plugins.discard(name)
        except Exception as e:
            logger.error(f"[事件中心] 插件 {name} 订阅同步失败(active={active}): {e}")

    @staticmethod
    async def _invoke(ref: str) -> None:
        fn = resolve_callable(ref)
        result = fn()
        if inspect.isawaitable(result):
            await result

    # ---------- 后台自定义订阅 ----------

    async def bind_manual_subscriptions(self) -> None:
        try:
            subs = await EventSubscription.filter(source="manual", is_enabled=True).all()
        except Exception as e:
            logger.warning(f"[事件中心] 读取自定义订阅失败(表可能未创建): {e}")
            return
        for sub in subs:
            await self.bind_manual(sub)

    async def bind_manual(self, sub: EventSubscription) -> bool:
        """把一条 manual 订阅包装成可启停的受控处理器并注册到总线。"""
        if not sub.handler_ref:
            return False
        if sub.name in self._wrapped:
            return True
        try:
            handler = resolve_callable(sub.handler_ref)
        except Exception as e:
            logger.error(f"[事件中心] 解析 {sub.handler_ref} 失败: {e}")
            return False

        sub_name = sub.name

        async def guarded(*, event_name: str | None = None, **kwargs: Any):
            if not await self._subscription_enabled(sub_name):
                return
            try:
                try:
                    result = handler(event_name=event_name, **kwargs)
                except TypeError:
                    result = handler(**kwargs)
                if inspect.isawaitable(result):
                    await result
            except Exception as e:
                # 订阅方失败隔离：绝不冒泡到发布方（PLR-14）
                logger.error(f"[事件中心] 订阅 {sub_name} 处理 {event_name} 失败: {e}")

        event_bus.subscribe(sub.event_name, guarded)
        self._wrapped[sub_name] = guarded
        return True

    async def unbind_manual(self, sub_name: str, event_name: str) -> None:
        wrapped = self._wrapped.pop(sub_name, None)
        if wrapped:
            event_bus.unsubscribe(event_name, wrapped)

    @staticmethod
    async def _subscription_enabled(sub_name: str) -> bool:
        sub = await EventSubscription.get_or_none(name=sub_name)
        return bool(sub and sub.is_enabled)

    async def set_enabled(self, sub: EventSubscription, enabled: bool) -> None:
        await EventSubscription.filter(id=sub.id).update(is_enabled=enabled)
        if sub.source == "manual":
            if enabled:
                await self.bind_manual(sub)
            else:
                # 不摘除总线注册，guarded 会按 DB 状态跳过，重新启用即时生效
                pass

    # ---------- 发布 ----------

    async def publish(
        self,
        event_name: str,
        payload: dict | None = None,
        *,
        idempotency_key: str | None = None,
        source_module: str = "event-center",
    ) -> dict:
        """平台统一发布入口：先校验规则，再交给事件总线（入队 ap.events）。"""
        problems = contract.validate_event_name(event_name)
        data = dict(payload or {})
        problems.extend(contract.validate_payload(data))
        if problems:
            raise ValueError("; ".join(problems))

        if idempotency_key and await self._idempotency_seen(idempotency_key):
            return {"published": False, "duplicate": True, "idempotency_key": idempotency_key}
        if idempotency_key:
            data["idempotency_key"] = idempotency_key

        await event_bus.publish(event_name, _source_module=source_module, **data)
        return {
            "published": True,
            "duplicate": False,
            "event_name": event_name,
            "idempotency_key": idempotency_key,
        }

    # ---------- 发布端幂等（D6：Redis 跨进程；不可用回退进程内 dict） ----------

    async def _idempotency_seen(self, key: str) -> bool:
        """记录并判断幂等键是否已出现。返回 True = 重复（本次发布被抑制）。"""
        now = time.time()
        # 清理过期键（两套存储共用同一 TTL）
        for k, ts in list(self._idempotency.items()):
            if now - ts > IDEMPOTENCY_TTL:
                self._idempotency.pop(k, None)
        try:
            from base.common.cache import RedisCache

            rc = await RedisCache.get_instance()
            redis_key = f"ap:event:idempotency:{key}"
            if await rc.exists(redis_key):
                return True
            await rc.set(redis_key, str(now), expire=IDEMPOTENCY_TTL)
            return False
        except Exception:
            # Redis 不可用：回退进程内 dict（多进程下退化为单进程去重，语义同旧实现）
            if key in self._idempotency:
                return True
            self._idempotency[key] = now
            return False


event_center = EventCenter()
