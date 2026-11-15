"""CRM 插件事件订阅声明（由 ``task/`` 目录自动发现，不再写 manifest.events）。"""
from __future__ import annotations

from base.common.taskiq_app.discovery import ap_subscribe


@ap_subscribe(
    "sales.paid",
    description="CRM：订单支付触发跟进任务",
    unregister_ref="unregister",
)
def register() -> None:
    """注册入口（幂等）：把真 handler 绑进 event_bus。"""
    from base.plugins.crm import register_crm_event_handlers

    return register_crm_event_handlers()


def unregister() -> None:
    from base.plugins.crm import unregister_crm_event_handlers

    return unregister_crm_event_handlers()
