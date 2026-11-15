"""Reconciler：把「声明式发现的周期作业」同步为 beat 的 scheduler_job 行。

改造（2026-11-15）
------------------
作业声明不再来自 ``manifest.json`` 的 ``jobs``，而来自插件 ``task/`` 目录
（以及平台 ``platform_jobs.py``）里 ``@broker.task`` 的 ``ap_*`` 标签。
``discovery.discover()`` 是 beat / worker 共用的唯一发现真源：

- 单一真源 = ``TaskSpec``（task_name / owner / ap_schedule / ap_requires /
  ap_interval_ref）；``job_id = task_name``，与既有 DB 行完全一致，零数据迁移。
- beat ``--startup`` 无参钩子 ``upsert_schedules()``：基线同步 + 周期后台重扫
  （捕获运行期插件启停 / interval_ref 变更，无需重启 beat）。
- worker 侧由 ``job_gate.apply_plugin_gate`` 在 task 执行前按
  ``is_plugin_active(owner)`` 复核，覆盖「停用至本轮重扫 pause」之间
  已投递到 ap.jobs 的消息。

trigger 必须用 ``PeriodicSchedule(interval=IntervalTrigger(...))`` 包装：
taskiq-beat 1.4.0 的 ``Scheduler.get_strategy()`` 读 ``trigger.strategy``，
裸传 ``IntervalTrigger`` 会抛 AttributeError，且 ``build_trigger()`` 会因
payload 缺 ``strategy`` 键失败（这是上一版实测到的启动期致命缺陷）。
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Tuple

from loguru import logger
from sqlalchemy import select
from taskiq_beat import IntervalTrigger, PeriodicSchedule, SchedulerJob

from base.common.dynamic_ref import resolve_callable
from base.common.plugin_contract import MIN_JOB_INTERVAL
from base.common.plugin_gate import is_plugin_active

from .config import settings
from .discovery import discover, scheduled_specs
from .scheduler import scheduler_app


async def _sync() -> None:
    """与 PG 中 scheduler_job 行 diff：targets → upsert(is_enabled=True)；stale → pause。"""
    if scheduler_app is None:
        logger.warning("[reconciler] scheduler_app 未初始化（缺 DB_URL），跳过同步")
        return

    specs = scheduled_specs(discover())
    # 平台作业是固定模块，恒应被发现。缺失说明发现器/导入整体异常——此时
    # 绝不能执行 diff pause，否则会误停全部既有调度行（fail-safe）。
    if not any(spec.is_platform for spec in specs):
        logger.error(
            "[reconciler] 未发现任何平台作业，判定为发现器异常；"
            "本轮跳过 diff（不暂停既有调度行）"
        )
        return

    targets: Dict[str, Tuple[object, int]] = {}
    for spec in specs:
        # (a) 插件启停门控：平台作业恒排程，插件作业按唯一双真门控
        if not spec.is_platform and not is_plugin_active(spec.owner):
            continue
        # (b) 依赖插件 AND 门控（原 manifest requires_plugins 语义）
        if spec.requires and not all(is_plugin_active(dep) for dep in spec.requires):
            continue

        interval = spec.schedule or MIN_JOB_INTERVAL
        # (c) interval_ref 每轮热重载（beat 无原生支持，放在 reconciler）
        if spec.interval_ref:
            try:
                interval = max(int(resolve_callable(spec.interval_ref)()), MIN_JOB_INTERVAL)
            except Exception as exc:
                logger.warning(
                    f"[reconciler] 作业 {spec.job_id} 的 ap_interval_ref "
                    f"({spec.interval_ref}) 解析失败，沿用 {interval}s: {exc}"
                )
        targets[spec.job_id] = (spec.task, interval)

    async with scheduler_app.session_factory() as session:
        for job_id, (task_obj, interval) in targets.items():
            await scheduler_app.single(
                task=task_obj, args=[], kwargs={}
            ).upsert(
                session,
                trigger=PeriodicSchedule(interval=IntervalTrigger(seconds=interval)),
                job_id=job_id,
                name=job_id,
                is_enabled=True,
            )
        # 清理（禁用 / 依赖缺失 / 声明被移除）：pause（beat 不再投递，保留运行历史）
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
