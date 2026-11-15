"""MES 插件事件处理器（真 handler + 装卸入口）。

2026-11-15 改造
----------------
本模块原先的 ``register_event_handlers()`` 无任何调用点（死代码）。现在由
``base/plugins/mes/task/subscriptions.py`` 的 ``@ap_subscribe`` 声明驱动，
事件中心按插件启停调用 ``register_event_handlers`` / ``unregister_event_handlers``：
注册幂等、注销对称，停用后 ``_handler_registry`` 不残留 MES handler。

原顶层 ``try/except ImportError`` 兜底已删除：``event_bus`` 是底座单例、
``WorkOrder`` / ``OperationLog`` 是本插件模型，导入失败应由发现器/事件中心记录并
隔离，而不是静默把订阅变成 no-op。
"""
from datetime import datetime
from typing import Any

from loguru import logger

from base.common.events.event_bus import event_bus
from base.plugins.mes.models.production import WorkOrder
from base.plugins.mes.models.operation_log import OperationLog


async def on_equipment_status_changed(**kwargs):
    equipment_code = kwargs.get("equipment_code")
    new_status = kwargs.get("new_status")
    work_center_code = kwargs.get("work_center_code")

    if not equipment_code or not new_status:
        return

    if new_status == "fault":
        work_orders = await WorkOrder.filter(
            equipment_code=equipment_code,
            status="processing"
        )
        for wo in work_orders:
            wo.status = "suspended"
            wo.suspend_reason = "equipment"
            wo.suspend_source = equipment_code
            wo.suspended_at = datetime.now()
            await wo.save()


async def on_quality_inspection_completed(**kwargs):
    wo_code = kwargs.get("wo_code")
    inspection_result = kwargs.get("inspection_result")

    if not wo_code or not inspection_result:
        return

    if inspection_result == "unqualified":
        wo = await WorkOrder.filter(wo_code=wo_code, status="processing").first()
        if wo:
            wo.status = "suspended"
            wo.suspend_reason = "quality"
            wo.suspend_source = kwargs.get("inspection_code", "")
            wo.suspended_at = datetime.now()
            await wo.save()


async def on_inventory_picking_done(**kwargs):
    """领料完成联动 —— **占位实现，当前不产生业务写操作**。

    原文件此处只读取 ``requisition_code`` / ``mo_code`` 两个入参后直接返回。
    本次改造只把它接入声明式发现（保持行为不变），业务逻辑待 MES 产品补实；
    未补实前该订阅注册成功但为空操作，不应被当作已实现的功能验收。
    """
    requisition_code = kwargs.get("requisition_code")
    mo_code = kwargs.get("mo_code")
    return None


async def on_inventory_receipt_done(**kwargs):
    """入库完成联动 —— **占位实现，当前不产生业务写操作**（说明同上）。"""
    receipt_code = kwargs.get("receipt_code")
    mo_code = kwargs.get("mo_code")
    return None


async def log_operation(entity_type: str, entity_id: int, action: str,
                        old_value: Any = None, new_value: Any = None,
                        operator: str = None, remark: str = None):
    await OperationLog.create(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        operator=operator,
        operated_at=datetime.now(),
        remark=remark
    )


# 一条事件 → 一个真 handler。注册/注销必须遍历同一张表，保证装卸对称。
_HANDLER_PAIRS = (
    ("equipment.status_changed", on_equipment_status_changed),
    ("quality.inspection_completed", on_quality_inspection_completed),
    ("inventory.picking_done", on_inventory_picking_done),
    ("inventory.receipt_done", on_inventory_receipt_done),
)

_registered = False


def register_event_handlers():
    """注册 MES 声明订阅（幂等，事件中心按插件启用调用）。"""
    global _registered
    if _registered:
        return
    for event_name, handler in _HANDLER_PAIRS:
        event_bus.subscribe(event_name, handler)
    _registered = True
    logger.info(f"[MES] 声明订阅已注册（{len(_HANDLER_PAIRS)} 条）")


def unregister_event_handlers():
    """注销 MES 声明订阅（事件中心按插件停用调用）。"""
    global _registered
    if not _registered:
        return
    for event_name, handler in _HANDLER_PAIRS:
        event_bus.unsubscribe(event_name, handler)
    _registered = False
    logger.info("[MES] 声明订阅已注销")
