"""插件包：显式注册插件管理器（T4.10）。

导入 `base.plugins` 不再创建插件管理器实例；进程启动时调用
`init_plugin_manager()`，其余位置通过 `get_plugin_manager()` 获取。
"""
from base.common.plugin_manager import (
    PluginInstance,
    PluginManager,
    get_plugin_manager,
    init_plugin_manager,
)

__all__ = [
    "PluginManager",
    "PluginInstance",
    "init_plugin_manager",
    "get_plugin_manager",
]
