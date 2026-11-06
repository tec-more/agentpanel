from typing import Optional, Dict, Any
from datetime import datetime

try:
    from base.common.events.event_bus import event_bus
    from base.plugins.mes.models.production import WorkOrder
    from base.plugins.mes.models.operation_log import OperationLog
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False
    event_bus = None
    WorkOrder = None
    OperationLog = None


async def on_equipment_status_changed(**kwargs):
    equipment_code = kwargs.get("equipment_code")
    new_status = kwargs.get("new_status")
    work_center_code = kwargs.get("work_center_code")

    if not equipment_code or not new_status:
        return

    if WorkOrder is None:
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

    if WorkOrder is None:
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
    requisition_code = kwargs.get("requisition_code")
    mo_code = kwargs.get("mo_code")


async def on_inventory_receipt_done(**kwargs):
    receipt_code = kwargs.get("receipt_code")
    mo_code = kwargs.get("mo_code")


async def log_operation(entity_type: str, entity_id: int, action: str,
                        old_value: Any = None, new_value: Any = None,
                        operator: str = None, remark: str = None):
    if OperationLog is None:
        return
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


def register_event_handlers():
    if not EVENT_BUS_AVAILABLE or event_bus is None:
        return

    event_bus.subscribe("equipment.status_changed", on_equipment_status_changed)
    event_bus.subscribe("quality.inspection_completed", on_quality_inspection_completed)
    event_bus.subscribe("inventory.picking_done", on_inventory_picking_done)
    event_bus.subscribe("inventory.receipt_done", on_inventory_receipt_done)