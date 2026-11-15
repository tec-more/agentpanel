"""事件注册表：订阅/发布的统一入口。

- 插件订阅来自 ``base/plugins/<plugin>/task/`` 下 ``@ap_subscribe`` 声明，
  由 ``base.common.taskiq_app.discovery`` 统一扫描发现（2026-11-15 起
  ``manifest.events`` 已废弃），随插件启用/禁用同步注册与注销；
- 后台新增的 manual 订阅按 handler_ref 动态绑定，支持单条即时启停；
- 发布统一经 EventCenter.publish 校验规则 → EventBusAdapter.publish 在事务内
  写 ``EventRecord(status=pending)``（Outbox），由 ``platform:outbox_relay``
  异步投递进 ``ap.events``；执行全部在 taskiq worker；
- 发布端幂等改由 ``event_records.idempotency_key`` 唯一约束保证（DB 同事务，
  替代原 Redis 300s 键）：重复键不产生第二条消息记录。
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

from loguru import logger

# W2-3：解析器下沉到 base/common，供事件中心与作业调度器共用。
# 这里保留同名再导出，既有 `from base.core.events.registry import resolve_callable`
# 的调用方不受影响。
from base.common.dynamic_ref import resolve_callable  # noqa: F401
from base.common.events.event_bus import event_bus
from base.core.events import contract
from base.core.events.models import EventSubscription

class EventCenter:
    def __init__(self) -> None:
        self._bound_plugins: set[str] = set()
        self._bootstrapped: set[str] = set()
        # 绑定时记下注销入口：即使插件目录后来被移除/发现失败，停用时仍能对称摘除
        self._unregister_refs: dict[str, str] = {}
        self._wrapped: dict[str, Callable] = {}

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

        声明真源是 ``task/`` 目录的 ``@ap_subscribe``，不再读 manifest.events。
        """
        try:
            from base.common.plugin_gate import active_plugin_names
            from base.common.taskiq_app.discovery import discover_event_subscriptions

            owners = {spec.owner for spec in discover_event_subscriptions()}
            if not owners:
                logger.warning("[事件中心] 未发现任何 @ap_subscribe 订阅声明（本轮跳过同步）")
            for name in sorted(set(active_plugin_names()) & owners):
                await self.sync_plugin(name, active=True)
        except Exception as e:
            logger.error(f"[事件中心] 同步插件声明失败: {e}")
        await self.bind_manual_subscriptions()

    async def resync(self) -> None:
        """周期重扫（worker 长驻进程调用，与 beat reconciler 语义对齐）。

        API 进程的插件启停只改本进程注册表；worker 需靠周期 resync 收敛：
        - 新启用插件 → sync_plugin(active=True)（幂等，register_ref 只执行一次）
        - 已停用插件 → sync_plugin(active=False)（unregister_ref 摘除注册表）
        manual 订阅的启停由 guarded 包装器按 DB 状态即时生效，无需重扫。

        发现结果为空时**直接跳过本轮 diff**，避免目录挂载/导入异常导致全线误停用。
        """
        try:
            from base.common.plugin_gate import active_plugin_names
            from base.common.taskiq_app.discovery import discover_event_subscriptions

            owners = {spec.owner for spec in discover_event_subscriptions()}
            if not owners:
                logger.warning("[事件中心] resync: 订阅声明为空，跳过本轮 diff")
                return
            active = set(active_plugin_names()) & owners
            for name in list(self._bound_plugins):
                if name not in active:
                    await self.sync_plugin(name, active=False)
            for name in sorted(active):
                await self.sync_plugin(name, active=True)
        except Exception as e:
            logger.warning(f"[事件中心] resync 失败(下一轮重试): {e}")

    async def sync_plugin(
        self, name: str, manifest: dict | None = None, active: bool = True
    ) -> None:
        """插件启用/禁用时由 plugin_manager 调用：装卸对称、可重复执行。

        ``manifest`` 仅为兼容旧调用点保留，**不再读取**；声明真源是 ``task/``
        目录下的 ``@ap_subscribe``（``discovery.discover_event_subscriptions``）。
        """
        from base.common.taskiq_app.discovery import event_specs_by_owner

        specs = event_specs_by_owner(name)
        head = specs[0] if specs else None
        if (
            not specs
            and name not in self._bound_plugins
            and name not in self._unregister_refs
        ):
            # fail-safe：发现失败时不误停用既有订阅行、不误调注册
            return

        try:
            if active and head and head.bootstrap and name not in self._bootstrapped:
                await self._invoke(head.bootstrap)
                self._bootstrapped.add(name)

            for spec in specs:
                problems = contract.validate_event_name(spec.event_name)
                if problems:
                    logger.warning(f"[事件中心] 插件 {name} 声明被忽略: {problems}")
                    continue
                defaults = {
                    "event_name": spec.event_name,
                    "subscriber": name,
                    "handler_ref": spec.handler_ref,
                    "source": "declared",
                    "is_enabled": active,
                    "is_system": True,
                    "description": spec.description,
                }
                sub = await EventSubscription.filter(name=spec.sub_name).first()
                if sub:
                    await EventSubscription.filter(id=sub.id).update(
                        event_name=spec.event_name,
                        subscriber=name,
                        handler_ref=spec.handler_ref,
                        source="declared",
                        is_enabled=active,
                        is_system=True,
                    )
                else:
                    await EventSubscription.create(name=spec.sub_name, **defaults)

            if active:
                if head and name not in self._bound_plugins:
                    await self._invoke(head.register_ref)
                    self._bound_plugins.add(name)
                    if head.unregister_ref:
                        self._unregister_refs[name] = head.unregister_ref
            else:
                unregister_ref = self._unregister_refs.pop(
                    name, head.unregister_ref if head else None
                )
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

    # ---------- 发布（Outbox） ----------

    async def publish(
        self,
        event_name: str,
        payload: dict | None = None,
        *,
        idempotency_key: str | None = None,
        source_module: str = "event-center",
    ) -> dict:
        """平台统一发布入口：校验规则 → 事务内写 pending 消息记录。

        幂等由 ``event_records.idempotency_key`` 唯一约束在 DB 侧判定，
        与消息落库同一事务；不再依赖 Redis / 进程内 dict。
        """
        problems = contract.validate_event_name(event_name)
        data = dict(payload or {})
        problems.extend(contract.validate_payload(data))
        if problems:
            raise ValueError("; ".join(problems))

        # 幂等键走显式参数，不混进业务载荷；避免 **data 重复关键字。
        data.pop("idempotency_key", None)

        result = await event_bus.publish(
            event_name,
            idempotency_key=idempotency_key,
            _source_module=source_module,
            **data,
        )
        return {
            "published": result["published"],
            "duplicate": result["duplicate"],
            "event_name": event_name,
            "event_uuid": result.get("event_uuid"),
            "status": result.get("status"),
            "idempotency_key": idempotency_key,
        }


event_center = EventCenter()
