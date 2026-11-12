"""插件装配契约（单一路径契约来源）。

约定（与 base/app_wrapper.py 的剥离规则配套）：
1. 浏览器侧唯一合法 API 前缀是 ``/api``，由 ASGI 包装器剥离；
2. FastAPI 应用内部的插件路由一律以 ``/v1/`` 开头，**禁止**在
   ``APIRouter(prefix=...)`` 或 ``manifest.route_prefix`` 中再写 ``/api``；
3. 插件装配信息只能来自 manifest；目录不存在、路由文件无标准导出、
   前缀非法、零路由均视为声明与实装不一致，拒绝装配并给出可定位错误。

对应 v3.0 基线 AC-PLR-01-1 / AC-PLR-01-2、AC-PLR-13-2。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

# 浏览器侧前缀：只在这里定义一次，app_wrapper / 前端 / 文档都引用它
BROWSER_API_PREFIX = "/api"
# FastAPI 应用内部插件路由根的开头
INTERNAL_ROUTE_ROOT = "/v1/"
# 允许的内部接口前缀（harness app_internal 等，不走插件业务前缀）
INTERNAL_ROUTE_ALLOWED = ("/internal/",)

REQUIRED_FIELDS: tuple[str, ...] = ("name", "route_prefix", "routes")
RECOMMENDED_FIELDS: tuple[str, ...] = ("version", "display_name", "menus", "permissions")
EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
# W2-3 定时任务声明：作业名插件内唯一，handler_ref 为 module:callable
JOB_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HANDLER_REF_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
    r":[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)
MIN_JOB_INTERVAL = 30


class ContractViolation(Exception):
    """声明与实装不一致，装配必须被拒绝。"""

    def __init__(self, plugin: str, problems: list[str]):
        self.plugin = plugin
        self.problems = problems
        joined = "; ".join(problems)
        super().__init__(f"插件 {plugin} 装配契约校验失败: {joined}")


def is_valid_event_name(event_name: str) -> bool:
    """事件名规则：小写点分多段，如 ``sales.paid`` / ``model.created``。"""
    return bool(EVENT_NAME_RE.match(event_name or ""))


def validate_jobs(jobs: Any) -> list[str]:
    """校验 manifest.jobs 声明（W2-3）。

    契约校验期**只验格式，不 import handler 模块**：避免校验动作本身执行插件代码。
    ``interval_ref`` 为可选字段，指向 ``module:callable``，调度器每轮 sleep 前调用，
    用于保持「间隔每轮重读、后台改配置热生效」的既有语义（如网关对账）。
    """
    problems: list[str] = []
    if jobs is None:
        return problems
    if not isinstance(jobs, list):
        return ["jobs 必须是数组"]
    seen: set[str] = set()
    for idx, job in enumerate(jobs):
        tag = f"jobs[{idx}]"
        if not isinstance(job, dict):
            problems.append(f"{tag} 必须是对象")
            continue

        name = job.get("name")
        if not isinstance(name, str) or not JOB_NAME_RE.match(name):
            problems.append(f"{tag}.name 非法（应为 ^[a-z][a-z0-9_]*$）: {name!r}")
        elif name in seen:
            problems.append(f"{tag}.name 在插件内重复: {name!r}")
        else:
            seen.add(name)

        for ref_field in ("handler_ref", "interval_ref"):
            ref = job.get(ref_field)
            if ref is None and ref_field == "interval_ref":
                continue  # 可选
            if not isinstance(ref, str) or not HANDLER_REF_RE.match(ref):
                problems.append(
                    f"{tag}.{ref_field} 非法（应为 module:callable）: {ref!r}"
                )

        interval = job.get("interval_seconds")
        if isinstance(interval, bool) or not isinstance(interval, int) or interval < MIN_JOB_INTERVAL:
            problems.append(
                f"{tag}.interval_seconds 必须是 ≥{MIN_JOB_INTERVAL} 的整数: {interval!r}"
            )

        requires = job.get("requires_plugins")
        if requires is not None:
            if not isinstance(requires, list) or any(
                not isinstance(dep, str) or not dep for dep in requires
            ):
                problems.append(f"{tag}.requires_plugins 必须是非空字符串数组")
    return problems


def validate_no_browser_prefix(prefix: str) -> list[str]:
    """只校验不得重复声明浏览器侧 /api 前缀（用于路由文件内部的小前缀）。"""
    if prefix and BROWSER_API_PREFIX in prefix.split("/"):
        return [
            f"路由前缀含浏览器前缀 {BROWSER_API_PREFIX!r}: {prefix!r}"
            f"（由 app_wrapper 统一剥离，插件内不得重复声明）"
        ]
    return []


def validate_route_prefix(prefix: str, *, allow_internal: bool = False) -> list[str]:
    """校验 manifest 的 route_prefix，返回问题描述列表。"""
    problems: list[str] = []
    if not prefix:
        return problems
    if not prefix.startswith("/"):
        problems.append(f"route_prefix 必须以 / 开头: {prefix!r}")
    problems.extend(validate_no_browser_prefix(prefix))
    if allow_internal and prefix.startswith(INTERNAL_ROUTE_ALLOWED):
        return problems
    if not prefix.startswith(INTERNAL_ROUTE_ROOT):
        problems.append(
            f"route_prefix 必须以 {INTERNAL_ROUTE_ROOT} 开头: {prefix!r}"
        )
    return problems


def validate_manifest(name: str, manifest: dict[str, Any], plugin_dir: Path) -> list[str]:
    """校验 manifest 声明。返回问题描述列表（空列表表示通过）。"""
    problems: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in manifest or manifest.get(field) in (None, "", []):
            problems.append(f"缺少必填字段 {field}")

    prefix = manifest.get("route_prefix", "")
    problems.extend(validate_route_prefix(prefix))

    routes = manifest.get("routes") or []
    if not isinstance(routes, list):
        problems.append("routes 必须是目录路径数组")
        routes = []
    for route_path in routes:
        target = plugin_dir / str(route_path)
        if not target.is_dir():
            problems.append(
                f"routes 声明的目录不存在: {route_path!r}"
                f"（routes 必须指向目录，不能指向 .py 文件）"
            )

    internal_routes = manifest.get("internal_routes") or []
    if not isinstance(internal_routes, list):
        problems.append("internal_routes 必须是目录路径数组")
        internal_routes = []
    for route_path in internal_routes:
        target = plugin_dir / str(route_path)
        if not target.is_dir():
            problems.append(f"internal_routes 声明的目录不存在: {route_path!r}")

    declared_events = (manifest.get("events") or {}).get("subscribe") or []
    if not isinstance(declared_events, list):
        problems.append("events.subscribe 必须是数组")
    else:
        for item in declared_events:
            if isinstance(item, dict):
                event_name = item.get("event_name", "")
            else:
                event_name = str(item)
            if not is_valid_event_name(event_name):
                problems.append(f"非法事件名: {event_name!r}（应为小写点分格式）")

    # W2-3：定时任务声明与路由/事件同级硬校验，声明非法一律拒绝装配
    problems.extend(validate_jobs(manifest.get("jobs")))

    if manifest.get("name") and manifest["name"] != name:
        problems.append(
            f"manifest.name={manifest['name']!r} 与插件目录名 {name!r} 不一致"
        )
    return problems


def router_attr_candidates(route_file: Path) -> list[str]:
    """返回路由文件允许导出的变量名（按优先级）。

    兼容内部接口的历史命名 ``app_{stem}``（如 app_touch_router）。
    """
    stem = route_file.stem
    if stem.endswith("_router"):
        return [stem, f"app_{stem}", "router"]
    return [f"{stem}_router", f"app_{stem}_router", "router"]


def describe_problems(name: str, problems: Iterable[str]) -> str:
    return f"插件 {name} 声明与实装不一致: " + "; ".join(problems)
