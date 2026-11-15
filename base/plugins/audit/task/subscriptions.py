"""审计插件事件订阅声明（由 ``task/`` 目录自动发现）。

旧 ``manifest.events`` 的 register_ref / unregister_ref / subscribe 全部收拢到
此处的 ``@ap_subscribe`` 声明；注册函数体只做延迟 import，避免 app 启动期
发现器扫描时加载 ORM 补丁等重模块。
"""
from __future__ import annotations

from base.common.taskiq_app.discovery import ap_subscribe


@ap_subscribe(
    "model.created",
    "model.updated",
    "model.deleted",
    "user.login",
    "user.logout",
    description="审计：ORM 数据变更与登录事件落库",
    unregister_ref="unregister",
)
def register() -> None:
    """注册入口（幂等）：把真 handler 绑进 event_bus 并安装 ORM 变更补丁。"""
    from base.plugins.audit.services.audit_subscriptions import (
        register_audit_subscriptions,
    )

    return register_audit_subscriptions()


def unregister() -> None:
    from base.plugins.audit.services.audit_subscriptions import (
        unregister_audit_subscriptions,
    )

    return unregister_audit_subscriptions()
