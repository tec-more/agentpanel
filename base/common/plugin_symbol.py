"""运行时按字符串解析插件符号，避免 base/common 静态/内联直接 import 插件实现。

base/common 是平台底座，按 PLR-13/15 零侵入原则不得直接依赖 ``base/plugins`` 内的
模型、异常等符号。所有需要引用插件符号的位置统一调用本模块，调用方据此实现插件
未安装/未启用时的降级，而不是在导入阶段就崩。

解析结果按完整路径缓存（模型/异常类为单例，插件禁用也不会被卸载，缓存安全）。
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Dict


class PluginSymbolUnavailable(Exception):
    """插件符号当前不可用（插件缺失 / 模块路径失效 / 符号不存在）。"""


_SYMBOL_CACHE: Dict[str, Any] = {}


def resolve_plugin_symbol(dotted_path: str, *, use_cache: bool = True) -> Any:
    """解析形如 ``base.plugins.customer.models.customer.Customer`` 的符号。

    Args:
        dotted_path: 模块路径 + ``.`` + 符号名的完整字符串。
        use_cache: 是否缓存解析结果（默认缓存）。

    Raises:
        PluginSymbolUnavailable: 模块或符号不可用时抛出，调用方据此降级。
    """
    if use_cache and dotted_path in _SYMBOL_CACHE:
        return _SYMBOL_CACHE[dotted_path]

    module_path, _, attr = dotted_path.rpartition(".")
    if not module_path or not attr:
        raise PluginSymbolUnavailable(f"非法插件符号路径: {dotted_path}")

    try:
        module = import_module(module_path)
    except ModuleNotFoundError as exc:  # 插件未安装 / 未启用
        raise PluginSymbolUnavailable(f"插件模块缺失: {module_path}") from exc

    try:
        symbol = getattr(module, attr)
    except AttributeError as exc:
        raise PluginSymbolUnavailable(f"插件符号缺失: {dotted_path}") from exc

    if use_cache:
        _SYMBOL_CACHE[dotted_path] = symbol
    return symbol
