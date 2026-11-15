"""声明式任务发现：beat / broker / worker 的**唯一注册真源**。

改造背景（2026-11-15）
----------------------
此前一个周期作业要声明两次：``@broker.task`` 写 ``task_name``/``queue_name``，
``manifest.json`` 的 ``jobs`` 再写 ``handler_ref``/``interval_seconds``/
``requires_plugins``/``interval_ref``。beat 的 reconciler、worker 的
tasks_registry 各自解析一遍 manifest，声明与实装容易漂移。

现在统一为：插件 ``task/`` 目录下的 ``@broker.task`` **自带声明标签**，
本模块扫描目录 + import 触发注册 + 从 broker 任务表抽取 ``TaskSpec``。
三个进程消费同一份发现结果：

======== ================================================================
进程      用法
======== ================================================================
beat      ``scheduled_specs(discover())`` → 写 ``scheduler_job`` 行
worker    ``discover()`` → 全部任务注册 + 事件订阅绑定 + 插件门控装配
app       不参与发现（只发布事件、只管插件启停状态）
======== ================================================================

声明标签（全部挂在 ``@broker.task`` 的 ``**labels`` 上，统一 ``ap_`` 前缀）
--------------------------------------------------------------------------
``ap_schedule``      int，周期秒数。**有此标签 = 参与 beat 排程**；
                     无此标签 = 仅注册为可被调用的 task，不自动调度。
                     插件作业 ≥MIN_JOB_INTERVAL(30s)；平台作业(platform:*)≥1s，
                     供 Outbox relay 这类秒级基础设施轮询使用。
``ap_interval_ref``  ``"module:callable"``，可选。beat 每轮重扫时调用，
                     用于「间隔热重载」（如 harness 网关对账）。
``ap_requires``      插件名数组，可选。依赖插件未激活 → 不进入 targets。
``ap_description``   说明文本，可选（写入调度行的 description 预留）。

``task_name`` 同时就是 ``scheduler_job.job_id``（现有 DB 行的 job_id 本来就是
``owner:name`` 形式），所以本次改造**零数据迁移**，已存在的调度行会原地更新。

事件订阅声明（2026-11-15 第二次统一）
--------------------------------------
``manifest.json`` 的 ``events`` 段同样废弃。事件订阅声明与周期作业放在**同一批**
``task/`` 目录文件里，用 ``@ap_subscribe`` 装饰注册函数：

    @ap_subscribe("sales.paid", description="...", unregister_ref="unregister")
    def register():
        from base.plugins.xxx.services import handlers
        return handlers.register()

被装饰函数即旧 ``manifest.events.register_ref`` 指向的注册入口（把真 handler
绑进 ``event_bus``），发现器从函数属性读出声明并产出 ``EventSubSpec``。
``base.core.events.registry.EventCenter`` 按 owner 消费这些 spec 完成装卸，
app / worker 两个进程走同一份发现结果。

目录约定
--------
插件作业放 ``base/plugins/<plugin>/task/*.py``；为兼容未迁移的第三方插件，
依次回退识别 ``tasks/``、``jobs/``（同一插件只取第一个存在的目录）。
平台级作业固定从 ``base.common.taskiq_app.platform_jobs`` 发现，owner 恒为
``platform``，不受插件启停门控影响。
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, TypeVar

from loguru import logger

from base.common.plugin_contract import MIN_JOB_INTERVAL, is_valid_event_name

from .broker import broker

_F = TypeVar("_F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# 声明标签常量
# ---------------------------------------------------------------------------
LABEL_PREFIX = "ap_"
LABEL_SCHEDULE = "ap_schedule"
LABEL_INTERVAL_REF = "ap_interval_ref"
LABEL_REQUIRES = "ap_requires"
LABEL_DESCRIPTION = "ap_description"

# 事件订阅声明：@ap_subscribe 挂在注册函数上的属性名
SUBSCRIPTION_ATTR = "__ap_subscription_decl__"

# 平台作业：唯一不放在插件目录里的任务模块
PLATFORM_OWNER = "platform"
PLATFORM_MODULE = "base.common.taskiq_app.platform_jobs"

# 插件目录（与 plugin_gate._PLUGINS_DIR 同源：base/plugins）
PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"
# 目录优先级：新约定 task/，兼容 tasks/ 与历史 jobs/
TASK_DIR_CANDIDATES = ("task", "tasks", "jobs")

_JOBS_QUEUE = "ap.jobs"
# MIN_JOB_INTERVAL 由 plugin_contract 提供（与历史契约同源，避免第二套阈值）。
# 平台作业承担 Outbox relay 这类秒级基础设施轮询，单独放宽到 1s；
# 插件作业仍必须 ≥MIN_JOB_INTERVAL(30s)，避免业务插件把 beat 打满。
PLATFORM_MIN_JOB_INTERVAL = 1


@dataclass(frozen=True)
class TaskSpec:
    """一个 ``@broker.task`` 声明经发现后得到的完整描述。"""

    task_name: str
    owner: str
    queue: str
    module: str
    schedule: int | None
    interval_ref: str | None
    requires: tuple[str, ...]
    description: str
    # broker 里注册后的 decorated task 对象（beat 的 scheduler_app.single 需要它）
    task: Any = field(repr=False, compare=False)

    @property
    def job_id(self) -> str:
        """稳定调度行主键 = task_name（兼容既有 scheduler_job 行）。"""
        return self.task_name

    @property
    def scheduled(self) -> bool:
        return self.schedule is not None and self.queue == _JOBS_QUEUE

    @property
    def is_platform(self) -> bool:
        return self.owner == PLATFORM_OWNER


@dataclass(frozen=True)
class EventSubSpec:
    """一条 ``@ap_subscribe`` 声明经发现后得到的事件订阅描述。

    同一插件的多个事件会展开成多条 spec（与 ``event_subscriptions`` 表一行一事件
    对齐），``register_ref`` / ``unregister_ref`` / ``bootstrap`` 在组内相同，
    事件中心每个插件只调用一次。
    """

    owner: str
    event_name: str
    handler_ref: str
    register_ref: str
    unregister_ref: str | None
    bootstrap: str | None
    description: str
    module: str

    @property
    def sub_name(self) -> str:
        """DB 行主键，沿用 ``<owner>:<event_name>``（兼容既有数据，零迁移）。"""
        return f"{self.owner}:{self.event_name}"


# 进程内缓存：import 只需一次，但插件激活态 / interval_ref 每轮由调用方重算
_specs_cache: list[TaskSpec] | None = None
_event_specs_cache: list[EventSubSpec] | None = None


def iter_plugin_task_modules() -> list[tuple[str, str]]:
    """扫描插件 task 目录，返回 ``[(owner, dotted_module), ...]``（排序稳定）。

    - 只认带 ``manifest.json`` 的目录（插件身份的唯一标志）；
    - 同一插件只取优先级最高的任务目录，避免同名模块重复 import；
    - 跳过 ``__init__.py`` 与 ``_`` 前缀的 helper 模块；
    - **不检查插件是否启用**：禁用插件的任务也必须注册进 broker，
      否则启用瞬间 beat 投递的消息会找不到 task（沿用原 tasks_registry 语义）。
    """
    result: list[tuple[str, str]] = []
    if not PLUGINS_DIR.is_dir():
        logger.warning(f"[task discovery] 插件目录不存在: {PLUGINS_DIR}")
        return result

    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or not (plugin_dir / "manifest.json").is_file():
            continue
        owner = plugin_dir.name
        task_dir = next(
            (plugin_dir / candidate for candidate in TASK_DIR_CANDIDATES
             if (plugin_dir / candidate).is_dir()),
            None,
        )
        if task_dir is None:
            continue
        for path in sorted(task_dir.glob("*.py")):
            if path.name == "__init__.py" or path.name.startswith("_"):
                continue
            result.append(
                (owner, f"base.plugins.{owner}.{task_dir.name}.{path.stem}")
            )
    return result


def iter_all_modules() -> list[tuple[str, str]]:
    """平台作业 + 全部插件作业模块（平台在最前，保证基础任务先注册）。"""
    return [(PLATFORM_OWNER, PLATFORM_MODULE), *iter_plugin_task_modules()]


def _import_modules(modules: list[tuple[str, str]]) -> int:
    """逐个 import 触发 ``@broker.task`` 注册；单模块失败隔离，不影响其它插件。"""
    imported = 0
    for owner, module_path in modules:
        try:
            importlib.import_module(module_path)
            imported += 1
        except Exception as exc:
            # 失败隔离：一个插件的作业模块坏了，不该让整个 worker/beat 起不来
            logger.error(
                f"[task discovery] 插件 {owner} 作业模块 {module_path} 导入失败"
                f"（已隔离，其任务不会被注册）: {exc}"
            )
    return imported


def _owner_of(module: str, task_name: str, module_prefixes: dict[str, str]) -> str:
    """优先按模块路径归属插件（防止 task_name 写错 owner），兜底用 task_name 前缀。"""
    if module == PLATFORM_MODULE or module.startswith(PLATFORM_MODULE + "."):
        return PLATFORM_OWNER
    for prefix, owner in module_prefixes.items():
        if module.startswith(prefix):
            return owner
    head, sep, _ = task_name.partition(":")
    return head if sep else ""


def _validate_labels(task_name: str, labels: dict[str, Any]) -> list[str]:
    """声明标签校验（替代旧 plugin_contract.validate_jobs）。

    只做格式校验，不 import 任何业务模块；非法声明记日志并**跳过该任务**，
    避免把错误周期写进 scheduler_job。
    """
    problems: list[str] = []
    owner = task_name.partition(":")[0]
    min_interval = (
        PLATFORM_MIN_JOB_INTERVAL if owner == PLATFORM_OWNER else MIN_JOB_INTERVAL
    )
    schedule = labels.get(LABEL_SCHEDULE)
    if schedule is not None:
        if isinstance(schedule, bool) or not isinstance(schedule, int) or schedule < min_interval:
            problems.append(
                f"{LABEL_SCHEDULE} 必须是 ≥{min_interval} 的整数: {schedule!r}"
            )
    ref = labels.get(LABEL_INTERVAL_REF)
    if ref is not None and (not isinstance(ref, str) or ":" not in ref):
        problems.append(f"{LABEL_INTERVAL_REF} 必须是 module:callable: {ref!r}")
    requires = labels.get(LABEL_REQUIRES)
    if requires is not None and (
        not isinstance(requires, (list, tuple))
        or any(not isinstance(dep, str) or not dep for dep in requires)
    ):
        problems.append(f"{LABEL_REQUIRES} 必须是非空字符串数组: {requires!r}")
    if not labels.get(LABEL_SCHEDULE) and ref:
        problems.append(f"{LABEL_INTERVAL_REF} 需与 {LABEL_SCHEDULE} 同时声明")
    if labels.get(LABEL_SCHEDULE) and not labels.get("queue_name"):
        problems.append("周期作业必须声明 queue_name=ap.jobs")
    if labels.get(LABEL_SCHEDULE) and labels.get("queue_name") != _JOBS_QUEUE:
        problems.append(
            f"周期作业必须落在 {_JOBS_QUEUE} 队列，实际 {labels.get('queue_name')!r}"
        )
    if not task_name or ":" not in task_name:
        problems.append(f"task_name 必须为 owner:name 形式: {task_name!r}")
    return problems


def collect_specs(modules: list[tuple[str, str]]) -> list[TaskSpec]:
    """从 broker 已注册任务表中抽取带 ``ap_*`` 声明标签的 TaskSpec。

    没有 ``ap_*`` 标签的任务（如 ``taskiq:dispatch``、纯调用型 task）不进入
    发现结果——它们仍注册在 broker，只是不参与调度/订阅装配。
    """
    module_prefixes = {
        f"base.plugins.{owner}.": owner
        for owner, _ in modules
        if owner != PLATFORM_OWNER
    }
    specs: list[TaskSpec] = []
    for task_name, task in broker.get_all_tasks().items():
        labels = getattr(task, "labels", None) or {}
        if not isinstance(labels, dict) or not any(
            key.startswith(LABEL_PREFIX) for key in labels
        ):
            continue

        problems = _validate_labels(task_name, labels)
        if problems:
            logger.error(
                f"[task discovery] 任务 {task_name} 声明非法，已跳过: "
                + "; ".join(problems)
            )
            continue

        original = getattr(task, "original_func", None)
        module = getattr(original, "__module__", "") or ""
        owner = _owner_of(module, task_name, module_prefixes)
        schedule = labels.get(LABEL_SCHEDULE)
        requires = labels.get(LABEL_REQUIRES) or []

        specs.append(
            TaskSpec(
                task_name=task_name,
                owner=owner,
                queue=str(labels.get("queue_name") or ""),
                module=module,
                schedule=int(schedule) if schedule is not None else None,
                interval_ref=labels.get(LABEL_INTERVAL_REF),
                requires=tuple(requires),
                description=str(labels.get(LABEL_DESCRIPTION) or ""),
                task=task,
            )
        )
    return sorted(specs, key=lambda spec: spec.task_name)


def discover(*, force: bool = False) -> list[TaskSpec]:
    """统一发现入口（幂等、进程内缓存）。

    ``force=True`` 强制重新扫描目录并重建缓存，供测试或热加载新插件目录使用。
    注意：插件「启用/禁用」与 ``interval_ref`` 每轮变化**不走缓存**，
    分别由 ``is_plugin_active`` / ``resolve_callable`` 在调用点实时计算。
    """
    global _specs_cache
    if _specs_cache is not None and not force:
        return _specs_cache

    modules = iter_all_modules()
    imported = _import_modules(modules)
    _specs_cache = collect_specs(modules)
    scheduled = sum(1 for spec in _specs_cache if spec.scheduled)
    logger.info(
        f"[task discovery] 发现 {len(_specs_cache)} 个声明任务"
        f"（其中周期作业 {scheduled} 个），已导入 {imported}/{len(modules)} 个模块"
    )
    return _specs_cache


# ---------------------------------------------------------------------------
# 事件订阅声明（@ap_subscribe）—— 与周期作业共用同一批 task/ 模块扫描
# ---------------------------------------------------------------------------


def ap_subscribe(
    *events: str,
    description: str = "",
    unregister_ref: str | None = None,
    bootstrap: str | None = None,
) -> Callable[[_F], _F]:
    """装饰插件事件注册函数，声明订阅哪些事件以及如何装卸。

    - ``events``         事件名列表（小写点分，见 ``plugin_contract.is_valid_event_name``）；
    - ``unregister_ref`` 注销入口，可只写本模块内函数名（自动补模块前缀），
      也可写完整 ``module:callable``；
    - ``bootstrap``      可选的一次性启动钩子（语义同旧 ``manifest.events.bootstrap``）；
    - ``description``    写入 ``event_subscriptions.description`` 的说明文本。

    被装饰函数**保持原样**（签名/返回值不变），只多一个声明属性；它仍由事件中心
    作为 ``register_ref`` 调用，函数体负责把真 handler 绑进 ``event_bus``。
    声明与注册入口同处 ``task/`` 目录，发现器 import 后自动读取。
    """

    def decorate(fn: _F) -> _F:
        setattr(
            fn,
            SUBSCRIPTION_ATTR,
            {
                "events": tuple(events),
                "description": description,
                "unregister_ref": unregister_ref,
                "bootstrap": bootstrap,
            },
        )
        return fn

    return decorate


def _qualify(ref: str | None, module: str) -> str | None:
    """把 ``"unregister"`` 补成 ``"module:unregister"``。"""
    if not ref:
        return None
    return ref if ":" in ref else f"{module}:{ref}"


def _validate_subscription_decl(decl: dict[str, Any]) -> list[str]:
    """只做格式校验，不执行任何注册函数；非法声明记日志并跳过。"""
    problems: list[str] = []
    events = decl.get("events") or ()
    if not events:
        problems.append("未声明任何事件名")
    for event_name in events:
        if not isinstance(event_name, str) or not is_valid_event_name(event_name):
            problems.append(f"非法事件名: {event_name!r}（应为小写点分格式）")
    if len(set(events)) != len(events):
        problems.append("同一声明内事件名重复")
    for field_name in ("unregister_ref", "bootstrap"):
        ref = decl.get(field_name)
        if ref is not None and (
            not isinstance(ref, str)
            or not ref.strip()
            or ref.count(":") > 1
            or ref.startswith(":")
            or ref.endswith(":")
        ):
            problems.append(
                f"{field_name} 必须是 module:callable 或模块内函数名: {ref!r}"
            )
    return problems


def collect_event_subscriptions(
    modules: list[tuple[str, str]],
) -> list[EventSubSpec]:
    """从 task 模块中抽取 ``@ap_subscribe`` 声明（一事件一条 EventSubSpec）。

    只认**本模块定义**的函数（``__module__`` 匹配），避免 re-export 造成重复；
    单模块导入失败隔离，不影响其它插件。
    """
    specs: list[EventSubSpec] = []
    for owner, module_path in modules:
        if owner == PLATFORM_OWNER:
            continue  # 平台级模块不声明业务事件订阅
        try:
            module: ModuleType = importlib.import_module(module_path)
        except Exception as exc:
            logger.error(
                f"[task discovery] 插件 {owner} 模块 {module_path} 导入失败"
                f"（已隔离，其事件订阅不会被发现）: {exc}"
            )
            continue
        for attr_name, attr in vars(module).items():
            if getattr(attr, "__module__", None) != module_path:
                continue
            decl = getattr(attr, SUBSCRIPTION_ATTR, None)
            if not isinstance(decl, dict) or not callable(attr):
                continue
            problems = _validate_subscription_decl(decl)
            if problems:
                logger.error(
                    f"[task discovery] {module_path}:{attr_name} 订阅声明非法，已跳过: "
                    + "; ".join(problems)
                )
                continue
            register_ref = f"{module_path}:{attr_name}"
            for event_name in decl["events"]:
                specs.append(
                    EventSubSpec(
                        owner=owner,
                        event_name=event_name,
                        handler_ref=register_ref,
                        register_ref=register_ref,
                        unregister_ref=_qualify(decl.get("unregister_ref"), module_path),
                        bootstrap=_qualify(decl.get("bootstrap"), module_path),
                        description=str(decl.get("description") or ""),
                        module=module_path,
                    )
                )
    return sorted(specs, key=lambda spec: (spec.owner, spec.event_name))


def discover_event_subscriptions(*, force: bool = False) -> list[EventSubSpec]:
    """统一事件订阅发现入口（幂等、进程内缓存）。

    与 ``discover()`` 扫描同一批 ``task/`` 模块；新增插件目录或测试夹具后
    需 ``reset()`` / ``force=True`` 才能看到新声明。
    """
    global _event_specs_cache
    if _event_specs_cache is not None and not force:
        return _event_specs_cache

    modules = iter_all_modules()
    _event_specs_cache = collect_event_subscriptions(modules)
    owners = sorted({spec.owner for spec in _event_specs_cache})
    logger.info(
        f"[task discovery] 发现 {len(_event_specs_cache)} 条事件订阅声明，"
        f"覆盖插件 {owners}"
    )
    return _event_specs_cache


def event_specs_by_owner(
    owner: str, specs: list[EventSubSpec] | None = None
) -> list[EventSubSpec]:
    """按插件名过滤事件订阅声明。"""
    return [
        spec
        for spec in (specs if specs is not None else discover_event_subscriptions())
        if spec.owner == owner
    ]


def scheduled_specs(specs: list[TaskSpec] | None = None) -> list[TaskSpec]:
    """返回参与 beat 排程的任务（有 ap_schedule 且落 ap.jobs）。"""
    return [spec for spec in (specs if specs is not None else discover()) if spec.scheduled]


def specs_by_owner(owner: str, specs: list[TaskSpec] | None = None) -> list[TaskSpec]:
    """按插件名过滤（平台作业 owner 为 ``platform``）。"""
    return [
        spec for spec in (specs if specs is not None else discover())
        if spec.owner == owner
    ]


def reset() -> None:
    """清空发现缓存（测试用；不撤销 broker 里已注册的任务）。"""
    global _specs_cache, _event_specs_cache
    _specs_cache = None
    _event_specs_cache = None


__all__ = [
    "TaskSpec",
    "EventSubSpec",
    "ap_subscribe",
    "discover_event_subscriptions",
    "event_specs_by_owner",
    "collect_event_subscriptions",
    "SUBSCRIPTION_ATTR",
    "LABEL_SCHEDULE",
    "LABEL_INTERVAL_REF",
    "LABEL_REQUIRES",
    "LABEL_DESCRIPTION",
    "MIN_JOB_INTERVAL",
    "PLATFORM_MIN_JOB_INTERVAL",
    "PLATFORM_OWNER",
    "PLATFORM_MODULE",
    "PLUGINS_DIR",
    "discover",
    "scheduled_specs",
    "specs_by_owner",
    "collect_specs",
    "iter_all_modules",
    "iter_plugin_task_modules",
    "reset",
]
