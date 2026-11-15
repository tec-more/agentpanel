"""财务插件事件订阅声明（由 ``task/`` 目录自动发现，不再写 manifest.events）。"""
from __future__ import annotations

from base.common.taskiq_app.discovery import ap_subscribe


@ap_subscribe(
    "purchase.confirmed",
    "purchase.received",
    "purchase.payment",
    "sales.paid",
    "sales.receipt",
    "work_order.completed",
    "material.picked",
    "production.receipt",
    description="财务：业务单据事件生成凭证",
    unregister_ref="unregister",
)
def register() -> None:
    """注册入口（幂等）：把真 handler 绑进 event_bus。"""
    from base.plugins.finance.services.finance_event_handler import (
        register_finance_event_handlers,
    )

    return register_finance_event_handlers()


def unregister() -> None:
    from base.plugins.finance.services.finance_event_handler import (
        unregister_finance_event_handlers,
    )

    return unregister_finance_event_handlers()
