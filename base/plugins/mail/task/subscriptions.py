"""消息插件事件订阅声明（由 ``task/`` 目录自动发现，不再写 manifest.events）。"""
from __future__ import annotations

from base.common.taskiq_app.discovery import ap_subscribe


@ap_subscribe(
    "model.created",
    "model.updated",
    "model.deleted",
    description="消息：模型变更产生系统消息",
    unregister_ref="unregister",
)
def register() -> None:
    """注册入口（幂等）：把真 handler 绑进 event_bus。"""
    from base.plugins.mail.services.event_handler import register_mail_event_handlers

    return register_mail_event_handlers()


def unregister() -> None:
    from base.plugins.mail.services.event_handler import unregister_mail_event_handlers

    return unregister_mail_event_handlers()
