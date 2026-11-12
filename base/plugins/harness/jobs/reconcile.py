"""Harness 插件作业：网关记账对账（单轮，W2-3）。

- ``resolve_interval`` 由调度器在**每轮 sleep 前**调用（含首轮），保持原任务
  「间隔每轮重读、后台改配置热生效」的语义；
- ``run`` 内含业务级 gating 自查：网关或对账开关关闭时本轮直接返回，
  任务保留但不产生业务调用（与「插件被平台禁用 → 任务取消」是不同层）；
- 与手动接口复用同一幂等服务，重复执行不会重复插入差异。
"""
from __future__ import annotations


def resolve_interval() -> int:
    """读取对账间隔；非法值回退默认 600s，下限 30s（与契约一致）。"""
    from base.plugins.harness.services.gateway_config import reconciliation_config

    return max(int(reconciliation_config().get("interval_seconds") or 600), 30)


async def run() -> None:
    """执行一轮网关 vs 客户端上报对账（原 gateway_reconcile_task 的单轮逻辑）。"""
    from base.plugins.harness.services.gateway_config import (
        gateway_enabled,
        reconciliation_config,
    )
    from base.plugins.harness.services.reconcile_service import HarnessReconcileService

    if not (gateway_enabled() and reconciliation_config().get("enabled")):
        return None

    result = await HarnessReconcileService.execute(trigger="scheduled")
    stats = result.get("stats") or {}
    print(
        "[定时任务] 网关对账完成 "
        f"batch={result.get('batch_no')} diffs={stats.get('diffs', 0)} "
        f"created={stats.get('created', 0)} updated={stats.get('updated', 0)}"
    )
    return None
