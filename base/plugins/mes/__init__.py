"""MES（制造执行）插件。

事件订阅由 ``task/subscriptions.py`` 的 ``@ap_subscribe`` 声明，事件中心在插件
启用/禁用时装卸；真 handler 在 ``services/event_handlers.py``。

本插件 manifest 默认 ``is_installed=false`` / ``is_enabled=false``，因此声明会被
发现器扫描到，但只有管理员安装并启用 MES 后订阅才会真正注册生效。
"""
