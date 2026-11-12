"""审计插件订阅的声明式入口（供 manifest.events 引用）。

平台事件中心通过 ``handler_ref`` 动态解析本模块，不在 base/core 中硬编码插件名
与事件名；注册/注销幂等，避免 on_enable 与 on_startup 重复订阅。
"""
from __future__ import annotations

from loguru import logger

from base.common.events.event_bus import event_bus

_data_change_handler = None
_login_event_handler = None
_registered = False

DATA_EVENTS = ("model.created", "model.updated", "model.deleted")
LOGIN_EVENTS = ("user.login", "user.logout")


def register_audit_subscriptions() -> None:
    """注册 ORM 变更与登录事件订阅（幂等）。"""
    global _data_change_handler, _login_event_handler, _registered
    if _registered:
        return

    from base.plugins.audit.services.orm_event_service import register_orm_audit_handlers
    from base.plugins.audit.handlers.data_change_handler import DataChangeHandler
    from base.plugins.audit.handlers.login_event_handler import LoginEventHandler

    register_orm_audit_handlers()
    _data_change_handler = DataChangeHandler()
    _login_event_handler = LoginEventHandler()
    for event_name in DATA_EVENTS:
        event_bus.subscribe(event_name, _data_change_handler.handle)
    for event_name in LOGIN_EVENTS:
        event_bus.subscribe(event_name, _login_event_handler.handle)
    _registered = True
    logger.info("[audit] 声明订阅已注册（model.* / user.login|logout）")


def unregister_audit_subscriptions() -> None:
    """注销事件订阅；ORM monkey-patch 保留（无撤销路径，但不再产生订阅副作用）。"""
    global _registered
    if not _registered:
        return
    for event_name in DATA_EVENTS:
        if _data_change_handler:
            event_bus.unsubscribe(event_name, _data_change_handler.handle)
    for event_name in LOGIN_EVENTS:
        if _login_event_handler:
            event_bus.unsubscribe(event_name, _login_event_handler.handle)
    _registered = False
    logger.info("[audit] 声明订阅已注销")
