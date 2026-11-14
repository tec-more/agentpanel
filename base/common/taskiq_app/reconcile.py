"""ManifestReconciler：把 manifest 作业声明同步为 beat 的 scheduler_job 行。

- beat `--startup` 无参钩子 `upsert_schedules()`：基线同步 + 启动周期后台重扫
  （捕获运行期插件启停 / interval_ref 变更，无需重启 beat）。
- 单一真源 = scheduler_job 行；worker 侧 `is_plugin_active` 作兜底门控。
- 真实 task 对象来自插件模块（@broker.task 装饰后的产物），beat 侧 import 即注册。
"""
from __future__ import annotations

import asyncio
import importlib
import time
from typing import Dict, Tuple

from loguru import logger
from sqlalchemy import select
from taskiq_beat import IntervalTrigger, SchedulerJob

from base.common.dynamic_ref import resolve_callable
from base.common.plugin_contract import MIN_JOB_INTERVAL
from base.common.plugin_gate import is_plugin_active
from base.common.plugin_manager import (
    get_enabled_plugins_from_manifests,
    get_plugin_manager,
    init_plugin_manager,
)

from .config import settings
from .scheduler import scheduler_app


async def _sync() -> None:
    """与 PG 中 scheduler_job 行 diff：targets → upsert(is_enabled=True)；stale → pause。"""
    if scheduler_app is None:
        logger.warning("[reconciler] scheduler_app 未初始化（缺 DB_URL），跳过同步")
        return

    init_plugin_manager()
    mgr = get_plugin_manager()
    targets: Dict[str, Tuple[object, int]] = {}

    # (a) 插件作业：扫已启用插件的 manifest.jobs（requires_plugins AND 门控）
    for owner in get_enabled_plugins_from_manifests():
        manifest = mgr.get_manifest(owner) or {}
        for job in (manifest.get("jobs") or []):
            requires = job.get("requires_plugins") or []
            if not all(is_plugin_active(dep) for dep in requires):
                continue  # 依赖缺失 → 不进入 targets → 终态 pause
            job_id = f"{owner}:{job['name']}"
            mod, fn = job["handler_ref"].split(":", 1)
            try:
                task_obj = getattr(importlib.import_module(mod), fn)
            except Exception as exc:
                logger.error(f"[reconciler] 作业 {job_id} 的 task 对象解析失败: {exc}")
                continue
            interval = int(job.get("interval_seconds") or MIN_JOB_INTERVAL)
            # interval_ref 每轮热重载（beat 无原生支持，迁到 reconciler）
            if job.get("interval_ref"):
                try:
                    interval = max(int(resolve_callable(job["interval_ref"])()), MIN_JOB_INTERVAL)
                except Exception as exc:
                    logger.warning(
                        f"[reconciler] 作业 {job_id} interval_ref 解析失败，沿用 "
                        f"{interval}s: {exc}"
                    )
            targets[job_id] = (task_obj, interval)

    # (b) 平台作业：随 worker 永驻，不由 manifest 驱动
    from base.common.taskiq_app import platform_jobs

    for name in ("quota_reconcile", "quota_hold_cleanup"):
        targets[f"platform:{name}"] = (getattr(platform_jobs, name), 60)

    async with scheduler_app.session_factory() as session:
        for job_id, (task_obj, interval) in targets.items():
            await scheduler_app.single(
                task=task_obj, args=[], kwargs={}
            ).upsert(
                session,
                trigger=IntervalTrigger(seconds=interval),
                job_id=job_id,
                name=job_id,
                is_enabled=True,
            )
        # 清理（禁用/依赖缺失/已移除）：pause（beat 不再投递，保留运行历史）
        existing = {
            row.job_id
            for row in (await session.execute(select(SchedulerJob.id))).scalars()
        }
        for stale in existing - set(targets):
            await scheduler_app.pause(session, stale)
            logger.info(f"[reconciler] 暂停 stale 作业 {stale}")


async def upsert_schedules() -> None:
    """beat `--startup` 钩子（无参）：基线同步 + 周期后台重扫。

    M2 后旧 JobScheduler 已删除，beat 是唯一调度源，无条件排程；
    周期重扫捕获运行期插件启停 / interval_ref 变更（无需重启 beat）。
    """
    await _sync()
    logger.info(
        f"[reconciler] 基线同步完成，启动周期重扫（间隔 {settings.reconcile_interval}s）"
    )

    async def _periodic() -> None:
        # 周期重扫 + 刷新 beat 心跳：beat 是长驻进程，单次心跳 30s 后会过期，
        # 必须随周期循环持续刷新，否则 healthcheck 会误判健康 beat 为不健康。
        while True:
            try:
                await _sync()
            except Exception as exc:
                logger.warning(f"[reconciler] 周期同步失败: {exc}")
            try:
                from base.common.cache import RedisCache

                rc = await RedisCache.get_instance()
                await rc.set(
                    f"{settings.redis_key_prefix}beat:heartbeat", str(time.time()), ex=30
                )
            except Exception:
                pass
            await asyncio.sleep(settings.reconcile_interval)

    asyncio.create_task(_periodic())
