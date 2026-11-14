"""worker 生命周期（WORKER_STARTUP / WORKER_SHUTDOWN）。

与 app 解耦：worker 是独立进程，启动期自建连接池（同 asyncio loop，R2 落点）。
不依赖 app 的 lifespan；仅复用项目 canonical 初始化（`init_data` / `RedisCache` / 事件中心）。
"""
from __future__ import annotations

import asyncio
import time

from loguru import logger
from taskiq import TaskiqState
from taskiq.events import TaskiqEvents

from .broker import broker
from .config import settings


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def on_worker_startup(state: TaskiqState) -> None:
    """worker 子进程启动：建 Tortoise/Redis 连接池 + 注册全部 @broker.task + 写心跳键。"""
    logger.info("[taskiq worker] WORKER_STARTUP：初始化连接池与注册任务")

    # 1) Tortoise（复用项目 canonical init；RUN_DB_MIGRATIONS=false 时仅 init 不建表）
    try:
        from base.common.database import init_data

        await init_data()
    except Exception as exc:  # 单点失败不阻断 worker 启动（fail-open，与 app 一致）
        logger.error(f"[taskiq worker] Tortoise 初始化失败: {exc}")

    # 2) Redis 预热（使 is_plugin_active 等门控生效）
    try:
        from base.common.cache import RedisCache

        await RedisCache.get_instance()
    except Exception as exc:
        logger.warning(f"[taskiq worker] Redis 预热失败（降级）: {exc}")

    # 3) 事件中心（M3 负载关键）：register_ref + bind_manual 填充进程内订阅注册表，
    #    dispatch 任务按该注册表取 handler 执行。失败不阻断启动，但事件消费将不可用。
    try:
        from base.core.events.registry import event_center

        await event_center.initialize()
    except Exception as exc:
        logger.error(f"[taskiq worker] 事件中心初始化失败（事件消费不可用）: {exc}")

    # 3.5) 周期 resync：API 进程的插件启停不会同步到 worker，靠本循环收敛
    #      （新启用 → register_ref 幂等补注册；已停用 → unregister_ref 摘除），
    #      语义与 beat reconciler 的作业重扫对齐。
    async def _resync_loop() -> None:
        while True:
            await asyncio.sleep(settings.reconcile_interval)
            try:
                from base.core.events.registry import event_center

                await event_center.resync()
            except Exception as exc:
                logger.warning(f"[taskiq worker] 事件注册表 resync 失败(下一轮重试): {exc}")

    asyncio.create_task(_resync_loop())

    # 4) 导入全部作业模块 → 触发 @broker.task 注册（manifest 驱动，见 tasks_registry）
    from base.common.taskiq_app import tasks_registry  # noqa: F401  (import 即注册)

    # 5) 写 worker 心跳键（healthcheck 探活用），并启动周期刷新
    #    注意：心跳只写一次会在 30s 后过期，长驻 worker 必须周期刷新，
    #    否则 healthcheck 会误判健康进程为不健康。
    try:
        from base.common.cache import RedisCache

        rc = await RedisCache.get_instance()
        await rc.set(f"{settings.redis_key_prefix}worker:heartbeat", str(time.time()), ex=30)
        asyncio.create_task(_worker_heartbeat_loop(rc))
    except Exception:  # 心跳缺失不阻断启动
        pass

    registered = (
        list(broker.get_all_tasks().keys())
        if hasattr(broker, "get_all_tasks")
        else "?"
    )
    logger.info(f"[taskiq worker] 启动完成，已注册任务: {registered}")


async def _worker_heartbeat_loop(rc) -> None:
    """周期刷新 worker 心跳键（约每 10s 一次，ex=30），供 healthcheck 探活。

    worker 是长驻进程，单次写入 30s 后会过期导致误判；故在后台持续刷新。
    该任务由 WORKER_STARTUP 通过 asyncio.create_task 拉起，随 worker 事件循环存活。
    """
    try:
        while True:
            await rc.set(f"{settings.redis_key_prefix}worker:heartbeat", str(time.time()), ex=30)
            await asyncio.sleep(10)
    except Exception:  # 异常退出静默（不影响 worker 主任务）
        pass


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def on_worker_shutdown(state: TaskiqState) -> None:
    """worker 子进程关闭：排空并关闭 Tortoise 连接。"""
    logger.info("[taskiq worker] WORKER_SHUTDOWN：关闭连接池")
    try:
        from tortoise import Tortoise

        await Tortoise.close_connections()
    except Exception as exc:
        logger.error(f"[taskiq worker] 关闭 Tortoise 失败: {exc}")
