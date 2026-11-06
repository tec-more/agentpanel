from __future__ import annotations
import importlib
import pkgutil
import json
from fastapi import FastAPI , APIRouter
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Any
from functools import wraps
from typing import List, Optional
from base.common.log import log


def _is_plugin_enabled(plugin_name: str) -> bool:
    """检查插件是否已安装且激活"""
    plugins_dir = Path(__file__).parent.parent / "plugins"
    manifest_file = plugins_dir / plugin_name / "manifest.json"

    if not manifest_file.exists():
        return False

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            return manifest.get("is_installed", False) and manifest.get("is_enabled", False)
    except Exception:
        return False


def auto_discover_routers(
    app: FastAPI,
    base_package: str,
    router_variable_name: str = "router",
    skip_modules: Optional[List[str]] = None,
    check_plugin_status: bool = False
) -> None:
    """
    自动发现并注册 FastAPI 路由

    Args:
        app: FastAPI 应用实例
        base_package: 要扫描的基础包名（如 "base.core.users.api.v1"）
        router_variable_name: 路由实例的变量名（默认为 "router"）
        skip_modules: 要跳过的模块名列表
        check_plugin_status: 是否检查插件状态（用于 plugins 目录）
    """
    if skip_modules is None:
        skip_modules = ["__pycache__","middleware", "models", "schemas", "tests"]

    try:
        base_module = importlib.import_module(base_package)
    except ImportError as e:
        print(f"[ERROR] Failed to import base package {base_package}: {e}")
        return

    # 获取包的路径
    if not hasattr(base_module, "__path__"):
        print(f"[ERROR] {base_package} is not a valid package")
        return

    package_path = base_module.__path__[0]
    print(f"[SCAN] Scanning package path: {package_path}")

    routers_found = 0

    # 遍历包中的所有模块
    for finder, name, ispkg in pkgutil.iter_modules([package_path]):
        full_name = f"{base_package}.{name}"

        # 跳过指定的模块
        if any(skip in name for skip in skip_modules):
            continue

        # 如果需要检查插件状态（base.plugins 下的模块）
        if check_plugin_status and ispkg:
            if not _is_plugin_enabled(name):
                print(f"[SKIP] Inactive plugin: {name}")
                continue

        try:
            module = importlib.import_module(full_name)

            # 查找路由实例 - 支持多种命名方式
            # 1. 首先查找 {文件名}_router (插件规范)
            router_instance = None

            # 如果是普通模块文件（非包），尝试 {文件名}_router
            if not ispkg:
                file_router_name = f"{name}_router"
                router_instance = getattr(module, file_router_name, None)

            # 2. 如果没找到，查找 router_variable_name (通常是 "router")
            if router_instance is None:
                router_instance = getattr(module, router_variable_name, None)

            if isinstance(router_instance, APIRouter):
                # 注册路由到主应用
                app.include_router(router_instance)
                routers_found += 1
                print(f"[OK] Registered router: {full_name} -> {router_instance.prefix or '/'}")

            # 如果是包，递归扫描（支持子目录）
            if ispkg:
                num = _discover_in_subpackage(app, full_name, router_variable_name, routers_found, skip_modules)
                routers_found += num if num else 0
        except ImportError as e:
            print(f"[WARNING] Failed to import module {full_name}: {e}")
        except Exception as e:
            print(f"[ERROR] Error processing module {full_name}: {e}")

    print(f"[DONE] Router auto-discovery completed, {routers_found} routers registered")

def _discover_in_subpackage(app: FastAPI, package_name: str, router_var: str, routers_found: int, skip_modules: List[str]):
    """递归发现子包中的路由"""
    try:
        sub_module = importlib.import_module(package_name)

        if not hasattr(sub_module, "__path__"):
            return

        for finder, name, ispkg in pkgutil.iter_modules(sub_module.__path__):
            full_name = f"{package_name}.{name}"

            if any(skip in name for skip in skip_modules):
                continue

            try:
                module = importlib.import_module(full_name)

                # 支持多种路由命名方式
                # 1. 对于普通 .py 文件（非包），尝试 {文件名}_router
                router_instance = None
                if not ispkg:
                    file_router_name = f"{name}_router"
                    router_instance = getattr(module, file_router_name, None)

                # 2. 如果没找到，查找 router_var (通常是 "router")
                if router_instance is None:
                    router_instance = getattr(module, router_var, None)

                if isinstance(router_instance, APIRouter):
                    app.include_router(router_instance)
                    routers_found += 1
                    print(f"[OK] Registered sub-package router: {full_name}")

                # 继续递归（如果是包）
                if ispkg:
                    num = _discover_in_subpackage(app, full_name, router_var, 0, skip_modules)
                    routers_found += num if num else 0

            except ImportError as e:
                print(f"[WARNING] Failed to import sub-module {full_name}: {e}")
        return routers_found
    except ImportError:
        return

def register_routers(app: FastAPI):
    # 自动注册 core 目录下的所有路由
    auto_discover_routers(app, base_package="base.core")

    # 插件路由由 plugin_manager 在 startup 时注册，不需要在这里注册
    # 这样避免了重复注册导致的 Duplicate Operation ID 警告