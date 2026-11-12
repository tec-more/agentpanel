"""平台统一作业调度器（W2-3 / AC-PLR-15-1·15-2·13-1）。

契约要点：
1. 插件作业**只**来自 ``manifest.jobs`` 声明，随插件启用/禁用装卸；平台作业
   （不依赖插件的公共层能力，如 quota 对账）由代码注册，使用保留键 ``__platform__``。
2. 调度器持有唯一的 ``_run_loop``：首轮先 sleep 再执行、``CancelledError`` 退出、
   普通异常记日志后继续下一轮 —— 与迁移前 6 个任务体的行为逐项等价。
   插件 handler 只实现**单轮**逻辑，不再自带 while 循环。
3. 单个作业的解析/执行失败被隔离，不阻断同插件其它作业、其它插件或应用启动
   （fail-open 于单个作业，fail-closed 于平台契约）。
4. 运行期禁用插件会 cancel 该插件全部 ``asyncio.Task`` 并等待收尾，补上此前
   「启动期判一次门控、之后禁用仍空转」的真实缺口。

间隔约定：
- ``interval_seconds`` 为 manifest 声明的基础间隔（下限 30 秒，契约层已校验）；
- 可选 ``interval_ref``（``module:callable``）在**每轮 sleep 前**调用，含首轮，
  用于保留「间隔每轮重读、后台改配置热生效」的既有语义（网关对账）；
- handler 可返回正整数覆盖下一轮间隔（契约允许的动态调度最小能力）。
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional

from loguru import logger

from base.common import plugin_contract
from base.common.dynamic_ref import resolve_callable

PLATFORM_KEY = "__platform__"


@dataclass
class JobSpec:
    """一个已解析、可执行的作业规格。"""

    owner: str
    name: str
    handler: Callable[..., Any]
    interval_seconds: int = 60
    interval_ref: Optional[str] = None
    requires_plugins: tuple[str, ...] = ()
    description: str = ""

    @property
    def key(self) -> str:
        return f"{self.owner}:{self.name}"


class JobScheduler:
    """进程内单例；由 lifespan 的 start_all/shutdown 与插件启停钩子驱动。"""

    def __init__(self) -> None:
        self._tasks: dict[str, list[asyncio.Task]] = {}
        self._platform_specs: list[JobSpec] = []
        self._ready = False

    @property
    def ready(self) -> bool:
        """启动期 load_enabled_plugins 内嵌的 enable 钩子据此静默跳过。"""
        return self._ready

    # ------------------------------------------------------------------
    # 平台作业（代码注册，不属于任何插件）
    # ------------------------------------------------------------------
    def register_platform_job(
        self,
        name: str,
        handler: Callable[..., Any],
        interval_seconds: int = 60,
        description: str = "",
    ) -> None:
        """注册/覆盖一个平台作业；同名重复注册保持唯一。"""
        self._platform_specs = [s for s in self._platform_specs if s.name != name]
        spec = JobSpec(
            owner=PLATFORM_KEY,
            name=name,
            handler=handler,
            interval_seconds=max(int(interval_seconds), plugin_contract.MIN_JOB_INTERVAL),
            description=description,
        )
        self._platform_specs.append(spec)
        if self._ready:
            self._spawn(spec)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def start_all(self) -> int:
        """lifespan 启动期调用：先装平台作业，再遍历已启用插件的 manifest.jobs。"""
        if self._ready:
            # 支持同一进程内重复进入 lifespan（回归脚本会这么做）
            await self.shutdown()

        from base.common.jobs import platform as platform_jobs

        platform_jobs.install(self)  # _ready 仍为 False，只登记不 spawn
        self._ready = True
        total = self._start_specs(self._platform_specs)

        from base.common.plugin_manager import get_plugin_manager

        manager = get_plugin_manager()
        for name in manager.get_enabled_plugins_from_manifests():
            total += await self._start_owner(name, manager.get_manifest(name) or {})
        logger.info(f"[作业调度] 装配完成：{total} 个作业，归属 {self.task_owners()}")
        return total

    async def start_plugin(self, name: str) -> int:
        """enable_plugin 钩子：装载该插件声明的全部作业，返回启动数。"""
        if not self._ready:
            logger.debug(
                f"[作业调度] 未就绪，插件 {name} 作业由 start_all 统一装载（启动期跳过）"
            )
            return 0
        await self.stop_plugin(name)  # 防重复装载（enable→disable→enable 循环）
        from base.common.plugin_manager import get_plugin_manager

        manifest = get_plugin_manager().get_manifest(name) or {}
        return await self._start_owner(name, manifest)

    async def stop_plugin(self, name: str) -> int:
        """disable_plugin 钩子：cancel 该插件全部任务并等待收尾，返回取消数。"""
        tasks = self._tasks.pop(name, [])
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:  # 收尾异常不阻断关闭流程
                logger.warning(f"[作业调度] 插件 {name} 作业收尾异常: {e}")
        if tasks:
            logger.info(f"[作业调度] 插件 {name} 已取消 {len(tasks)} 个作业")
        return len(tasks)

    async def shutdown(self) -> None:
        """lifespan 关闭期调用：cancel 全部作业（含平台作业），先于插件 shutdown。"""
        for name in list(self._tasks):
            await self.stop_plugin(name)
        self._tasks.clear()
        self._ready = False
        logger.info("[作业调度] 全部作业已关闭")

    # ------------------------------------------------------------------
    # 装载
    # ------------------------------------------------------------------
    async def _start_owner(self, owner: str, manifest: dict) -> int:
        jobs = manifest.get("jobs") or []
        if not jobs:
            return 0
        specs: list[JobSpec] = []
        from base.common.plugin_gate import is_plugin_active

        for job in jobs:
            if not isinstance(job, dict):
                logger.error(f"[作业调度] 插件 {owner} 的 jobs 含非对象项，已跳过")
                continue
            label = f"{owner}:{job.get('name')}"
            try:
                requires = tuple(job.get("requires_plugins") or ())
                missing = [dep for dep in requires if not is_plugin_active(dep)]
                if missing:
                    logger.info(
                        f"[作业调度] 作业 {label} 跳过（依赖插件未启用: {missing}）"
                    )
                    continue
                handler = resolve_callable(job["handler_ref"])
                specs.append(
                    JobSpec(
                        owner=owner,
                        name=job["name"],
                        handler=handler,
                        interval_seconds=max(
                            int(job["interval_seconds"]), plugin_contract.MIN_JOB_INTERVAL
                        ),
                        interval_ref=job.get("interval_ref"),
                        requires_plugins=requires,
                        description=job.get("description", ""),
                    )
                )
            except Exception as e:
                # 单作业失败隔离：不阻断同插件其它作业、其它插件与启动
                logger.error(f"[作业调度] 作业 {label} 装载失败（已隔离）: {e}")
        return self._start_specs(specs)

    def _start_specs(self, specs: list[JobSpec]) -> int:
        for spec in specs:
            self._spawn(spec)
        return len(specs)

    def _spawn(self, spec: JobSpec) -> None:
        task = asyncio.create_task(self._run_loop(spec), name=f"job:{spec.key}")
        self._tasks.setdefault(spec.owner, []).append(task)
        logger.info(
            f"[作业调度] 已装载作业 {spec.key}（间隔 {spec.interval_seconds}s）"
        )

    # ------------------------------------------------------------------
    # 通用 runner
    # ------------------------------------------------------------------
    async def _run_loop(self, spec: JobSpec) -> None:
        """复刻迁移前任务体：先 sleep 后执行、取消即退出、异常记日志不中断。"""
        interval = max(int(spec.interval_seconds), plugin_contract.MIN_JOB_INTERVAL)
        while True:
            try:
                resolved = await self._resolve_interval(spec)
                if resolved is not None:
                    interval = resolved
                await asyncio.sleep(interval)

                result = spec.handler()
                if inspect.isawaitable(result):
                    result = await result
                if (
                    isinstance(result, int)
                    and not isinstance(result, bool)
                    and result >= plugin_contract.MIN_JOB_INTERVAL
                ):
                    interval = result
            except asyncio.CancelledError:
                logger.info(f"[作业调度] 作业 {spec.key} 已取消")
                break
            except Exception as e:
                # 业务异常不中断任务：下一轮继续 sleep 后重试
                logger.exception(f"[作业调度] 作业 {spec.key} 执行失败（不中断）: {e}")

    @staticmethod
    async def _resolve_interval(spec: JobSpec) -> Optional[int]:
        """每轮（含首轮）重读 interval_ref；解析失败沿用基础间隔。"""
        if not spec.interval_ref:
            return None
        try:
            fn = resolve_callable(spec.interval_ref)
            value = fn()
            if inspect.isawaitable(value):
                value = await value
            return max(int(value), plugin_contract.MIN_JOB_INTERVAL)
        except Exception as e:
            logger.error(
                f"[作业调度] 作业 {spec.key} 间隔解析失败，沿用 {spec.interval_seconds}s: {e}"
            )
            return None

    # ------------------------------------------------------------------
    # 只读观测（回归断言使用）
    # ------------------------------------------------------------------
    def task_count(self, owner: Optional[str] = None) -> int:
        if owner is not None:
            return len([t for t in self._tasks.get(owner, []) if not t.done()])
        return sum(
            len([t for t in tasks if not t.done()]) for tasks in self._tasks.values()
        )

    def task_owners(self) -> dict[str, int]:
        return {
            owner: len([t for t in tasks if not t.done()])
            for owner, tasks in self._tasks.items()
        }


# 进程内单例：lifespan、plugin_manager 钩子与回归断言共用同一实例
job_scheduler = JobScheduler()


def register_platform_job(
    name: str,
    handler: Callable[..., Any],
    interval_seconds: int = 60,
    description: str = "",
) -> None:
    """便捷入口：注册一个不依赖插件的公共层作业。"""
    job_scheduler.register_platform_job(name, handler, interval_seconds, description)
