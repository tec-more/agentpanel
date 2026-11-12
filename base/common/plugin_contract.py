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
