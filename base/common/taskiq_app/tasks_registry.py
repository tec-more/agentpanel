"""worker 启动聚合 import：触发全部 ``@broker.task`` 注册（跨进程安全）。

改造（2026-11-15）：发现逻辑统一收敛到 ``discovery.discover()``。
此前本模块自己解析 ``manifest.jobs[*].handler_ref``，与 beat 的 reconciler
各读一遍 manifest；现在两者共用同一份 ``TaskSpec``：

- 扫描 ``base/plugins/<plugin>/task/*.py`` + 平台 ``platform_jobs.py``，
  import 即注册；**扫描全部已安装插件（不止当前启用）**，保证插件启用瞬间
  broker 里已有对应 task（reconciler 只给已启用插件建调度行）。
- 不依赖文件名推断 task_name，也不裸扫目录里的 helper 模块
  （``__init__.py`` / ``_*.py`` 跳过）。
- 单模块导入失败隔离，不影响其它插件。
- 注册完成后统一装配**执行期插件门控**（``job_gate.apply_plugin_gate``）：
  插件停用后 reconciler 周期 pause 存在 ≤reconcile_interval 窗口，已投递到
  ``ap.jobs`` 的消息在 worker 执行前按 ``is_plugin_active(owner)`` 复核。
"""
from __future__ import annotations

from loguru import logger

from .broker import broker  # 确保 broker 先就绪
from .discovery import TaskSpec, discover, scheduled_specs


def import_all_job_tasks() -> list[TaskSpec]:
    """导入全部作业模块触发 ``@broker.task`` 注册；worker 启动期调用（import 即执行）。

    返回发现到的全部声明任务（含不参与调度的纯调用型 task），便于
    WORKER_STARTUP 输出可核对的注册清单。
    """
    # 独立 worker 进程需先建插件管理器：事件中心 initialize/resync 会用到
    # get_plugin_manager()，此处保持与原实现一致的幂等初始化。
    try:
        from base.common.plugin_manager import init_plugin_manager

        init_plugin_manager()
    except Exception as exc:
        logger.warning(f"[tasks_registry] 插件管理器初始化失败（不阻断注册）: {exc}")

    specs = discover()
    scheduled = scheduled_specs(specs)
    if not scheduled:
        logger.warning(
            "[tasks_registry] 未发现任何周期作业——请确认插件 task/ 目录存在且 "
            "@broker.task 已带 ap_schedule 声明（否则 worker 将无作业可消费）"
        )

    registered = len(broker.get_all_tasks()) if hasattr(broker, "get_all_tasks") else "?"
    logger.info(
        f"[tasks_registry] 声明发现完成：{len(specs)} 个声明任务 / "
        f"{len(scheduled)} 个周期作业，broker 已注册 {registered} 个任务"
    )

    # 执行期兜底门控：reconciler 每 reconcile_interval 才重扫一次调度行，
    # 插件停用后这段窗口内已投递的 ap.jobs 消息仍会到达 worker；包装
    # task.original_func 让每次执行前复核 is_plugin_active(owner)。
    from base.common.taskiq_app.job_gate import apply_plugin_gate

    apply_plugin_gate(broker)
    return specs


# 模块被 import 即触发注册（worker 命令 import base.common.taskiq_app.jobs ->
# jobs 顶层 import tasks_registry -> 此处执行），保证早于 receiver 构建任务表。
import_all_job_tasks()

__all__ = ["broker", "import_all_job_tasks"]
