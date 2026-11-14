"""worker 启动聚合 import：触发全部 @broker.task 注册（跨进程安全）。

设计（manifest 驱动发现，取舍见 M1 拆解 §3.1 ②）：
- 单一真源 = 各插件 manifest.json 的 jobs[*].handler_ref（"module:callable"）。
- 扫描【所有已安装插件】（不止当前已启用），提取 module 段 import，
  确保任意插件的 @broker.task 都已注册——即便当前被禁用，未来启用后
  beat 投递 worker 也能执行（reconciler 只给已启用插件建调度行）。
- 不依赖文件名推断 task_name（由装饰器显式声明），也不裸扫 jobs/ 目录
  （避免误 import __init__.py / helper 模块）。
- 平台作业（base.common.taskiq_app.platform_jobs）不在任何 manifest，单独显式 import。
- 单模块导入失败隔离。
"""
from __future__ import annotations

import importlib
from typing import List

from loguru import logger

from base.common.plugin_manager import get_plugin_manager, init_plugin_manager
from base.common.taskiq_app.broker import broker  # 确保 broker 先就绪


def _discover_job_modules() -> List[str]:
    """返回所有已安装插件声明的作业模块路径（去重、保序）。"""
    init_plugin_manager()  # 幂等：独立 worker 进程需先建插件管理器
    mgr = get_plugin_manager()
    seen: dict[str, None] = {}
    for name in mgr.discover_plugins():
        manifest = mgr.get_manifest(name) or {}
        for job in (manifest.get("jobs") or []):
            ref = job.get("handler_ref")
            if not isinstance(ref, str) or ":" not in ref:
                logger.warning(
                    f"[tasks_registry] 插件 {name} 作业 {job.get('name')} 的 "
                    f"handler_ref 非法（应为 module:callable）: {ref!r}，已跳过"
                )
                continue
            seen.setdefault(ref.split(":", 1)[0], None)
    return list(seen)


def _import_one(module_path: str) -> None:
    try:
        importlib.import_module(module_path)
    except Exception as exc:  # 单模块失败隔离
        logger.error(
            f"[tasks_registry] 作业模块 {module_path} 导入失败（已隔离，"
            f"对应任务不会被 worker 注册）: {exc}"
        )


def import_all_job_tasks() -> None:
    """导入全部作业模块触发 @broker.task 注册；在 WORKER_STARTUP 调用一次。"""
    # 平台作业：随 worker 永驻，不由 manifest 驱动
    _import_one("base.common.taskiq_app.platform_jobs")
    # 插件作业：manifest 驱动发现（优于手写清单与裸 glob）
    modules = _discover_job_modules()
    if not modules:
        logger.warning(
            "[tasks_registry] 未发现任何插件作业模块——请确认 settings.base_path "
            "已配置且插件 manifest.jobs 已声明（否则 worker 将无任务可消费）"
        )
    for module_path in modules:
        _import_one(module_path)
    count = len(broker.get_all_tasks()) if hasattr(broker, "get_all_tasks") else "?"
    logger.info(f"[tasks_registry] 作业模块导入完成，broker 已注册 {count} 个任务")


# 模块被 import 即触发注册（worker 命令 import base.common.taskiq_app.jobs ->
# jobs 内 import tasks_registry -> 此处执行）
import_all_job_tasks()

__all__ = ["broker", "import_all_job_tasks"]
