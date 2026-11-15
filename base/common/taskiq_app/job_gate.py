"""worker 执行期插件门控（M2/M3 终态兜底，§9.3 偏差整改）。

问题：beat 的 reconciler 每 ``reconcile_interval``（默认 5s）重扫一次，插件停用后
调度行会被 ``pause``，但 pause 之前**已经投递到 ap.jobs 的消息**仍会到达 worker。
仅靠调度侧门控不够，worker 侧必须在执行前复核插件激活态，否则停用插件的作业
仍会被执行一次。

做法：worker 启动、全部 ``@broker.task`` 注册完成后，对 ``ap.jobs`` 队列上的作业
执行体统一包一层门控，执行前按 ``task_name`` 的 owner 段调用全平台唯一双真门控
``base.common.plugin_gate.is_plugin_active``。

判定口径：
- ``platform:*``（平台级恒启作业）与 ``taskiq:*``（事件 dispatch）恒放行；
- 其它 ``owner:name`` 需 ``is_plugin_active(owner)`` 为 True；
- 无法解析 owner（task_name 不含 ``:``）时放行，避免误杀；
- 门控内部异常 → 记 warning 并放行（fail-open，与 worker 启动期降级风格一致），
  避免 manifest 读取抖动导致全部作业静默不跑。

实现说明（基于 taskiq 0.13.0 源码核实）：``receiver`` 以
``task.original_func`` 作为执行目标，故包装该属性即可在**不改动各插件作业源码**
的前提下覆盖全部现有/新增作业；beat 侧 ``scheduler_app.single(task=...)`` 只读取
``task_name`` / ``labels``，包装对其无影响。新增插件作业无需自行加门控。
"""
from __future__ import annotations

import functools
import inspect
from typing import Any

from loguru import logger

from base.common.plugin_gate import is_plugin_active

_JOB_QUEUE = "ap.jobs"
_ALWAYS_ALLOWED_OWNERS = frozenset({"platform", "taskiq"})
_GATE_MARK = "_ap_plugin_job_gate"


def owner_of(task_name: str) -> str | None:
    """从 ``owner:name`` 形式 task_name 取 owner；无法解析返回 None。"""
    owner, sep, _ = task_name.partition(":")
    return owner if sep and owner else None


def is_job_allowed(task_name: str) -> bool:
    """执行前判定：平台/事件任务恒放行，插件作业按双真门控。"""
    owner = owner_of(task_name)
    if owner is None or owner in _ALWAYS_ALLOWED_OWNERS:
        return True
    try:
        return is_plugin_active(owner)
    except Exception as exc:  # fail-open：门控本身异常不阻断作业
        logger.warning(
            f"[taskiq gate] 作业 {task_name} 插件激活态判定失败，本轮放行: {exc}"
        )
        return True


def wrap_job_with_plugin_gate(task: Any) -> bool:
    """给单个 decorated task 装配执行期门控；返回是否执行了包装（幂等）。

    仅包装 ``queue_name == ap.jobs`` 的任务；事件队列与已包装任务跳过。
    """
    labels = getattr(task, "labels", None) or {}
    if labels.get("queue_name") != _JOB_QUEUE:
        return False
    original = getattr(task, "original_func", None)
    if original is None or getattr(original, _GATE_MARK, False):
        return False

    task_name = getattr(task, "task_name", "") or ""

    @functools.wraps(original)
    async def gated(*args: Any, **kwargs: Any) -> Any:
        if not is_job_allowed(task_name):
            logger.info(
                f"[taskiq gate] 作业 {task_name} 所属插件未激活，跳过本次执行"
            )
            return None
        result = original(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    setattr(gated, _GATE_MARK, True)
    task.original_func = gated
    return True


def apply_plugin_gate(broker: Any) -> int:
    """遍历 broker 已注册任务统一装配门控（worker 启动期调用一次）。

    返回实际包装的任务数；单个任务包装失败只记日志，不阻断 worker 启动。
    """
    try:
        tasks = broker.get_all_tasks()
    except Exception as exc:
        logger.error(f"[taskiq gate] 读取 broker 任务表失败，门控未装配: {exc}")
        return 0

    wrapped = 0
    for task_name, task in tasks.items():
        try:
            if wrap_job_with_plugin_gate(task):
                wrapped += 1
        except Exception as exc:
            logger.error(f"[taskiq gate] 作业 {task_name} 门控装配失败: {exc}")
    logger.info(
        f"[taskiq gate] 已为 {wrapped} 个 ap.jobs 作业装配执行期插件门控"
        f"（注册任务共 {len(tasks)} 个）"
    )
    return wrapped
