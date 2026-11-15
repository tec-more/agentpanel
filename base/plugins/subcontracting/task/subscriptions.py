"""委外插件事件订阅声明（由 ``task/`` 目录自动发现，不再写 manifest.events）。"""
from __future__ import annotations

from base.common.taskiq_app.discovery import ap_subscribe


@ap_subscribe(
    "mrp2.planned_order_confirmed",
    "inventory.picking_done",
    "inventory.receipt_done",
    description="委外：计划订单与库存事件",
    unregister_ref="unregister",
)
def register() -> None:
    """注册入口（幂等）：把真 handler 绑进 event_bus。"""
    from base.plugins.subcontracting import register_event_handlers

    return register_event_handlers()


def unregister() -> None:
    from base.plugins.subcontracting import unregister_event_handlers

    return unregister_event_handlers()
