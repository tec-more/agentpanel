"""MES 插件事件订阅声明（由 ``task/`` 目录自动发现，不再依赖任何 manifest 声明）。

改造背景（2026-11-15）
----------------------
原 ``base/plugins/mes/services/event_handlers.py::register_event_handlers()`` 订阅了
4 条事件，但全仓库无任何调用点（``mes/__init__.py`` 原为空文件），属历史死代码，
符合性检查报告 §2.2 与整改方案 W2-2 均已登记。本次把它接入统一发现机制：

- 声明写在本文件 ``@ap_subscribe``，由 ``base.common.taskiq_app.discovery`` 扫描；
- 事件中心按插件启停调用 ``register`` / ``unregister``，装卸对称；
- 真 handler 仍在 ``services/event_handlers.py``，此处只做延迟 import 的薄包装，
  避免发现阶段加载 ORM 模型等重模块。

注意：``mes`` 的 manifest 默认 ``is_installed=false`` / ``is_enabled=false``，
声明会被发现，但**只在插件启用后**才会注册生效，不擅自激活业务。
"""
from __future__ import annotations

from base.common.taskiq_app.discovery import ap_subscribe


@ap_subscribe(
    "equipment.status_changed",
    "quality.inspection_completed",
    "inventory.picking_done",
    "inventory.receipt_done",
    description="MES：设备/质检异常挂起工单，库存出入库事件联动",
    unregister_ref="unregister",
)
def register() -> None:
    """注册入口（幂等）：把真 handler 绑进 event_bus。"""
    from base.plugins.mes.services.event_handlers import register_event_handlers

    return register_event_handlers()


def unregister() -> None:
    """注销入口：与注册严格对称，插件停用后不残留 handler。"""
    from base.plugins.mes.services.event_handlers import unregister_event_handlers

    return unregister_event_handlers()
