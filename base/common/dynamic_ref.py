"""动态符号解析：``module:callable`` 引用（平台层与插件层共用）。

从 ``base/core/events/registry.py`` 下沉而来，使 ``base/common/jobs`` 可以复用
而不必反向依赖 ``base/core/events``（W2-3 / AC-PLR-13-1）。

约定：
- 格式为 ``module:callable``，冒号后允许点分路径（``module:Class.method``）；
- 采用运行期 importlib 动态导入，平台层不产生对插件实现的编译期依赖；
- 只做解析，不缓存、不吞异常；调用方按自身策略隔离失败。
"""
from __future__ import annotations

import importlib
import inspect
from typing import Callable


def resolve_callable(ref: str) -> Callable:
    """解析 ``module:callable`` 或 ``module:Class.method``。

    :raises ValueError: 引用格式非法
    :raises ImportError/AttributeError: 模块或属性不存在
    """
    module_name, _, attr_path = (ref or "").partition(":")
    if not module_name or not attr_path:
        raise ValueError(f"非法 handler_ref: {ref!r}，应为 module:callable")
    module = importlib.import_module(module_name)
    parts = attr_path.split(".")
    first = getattr(module, parts[0])
    if inspect.isclass(first):
        instance = first()
        return getattr(instance, parts[1]) if len(parts) > 1 else instance
    target = first
    for part in parts[1:]:
        target = getattr(target, part)
    return target
