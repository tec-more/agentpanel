from loguru import logger
from base.common.events.event_bus import event_bus
from base.plugins.subcontracting.services.subcontracting_order_service import SubcontractingOrderService


async def on_planned_order_confirmed(event_name: str = "", **kwargs):
    order_type = kwargs.get("order_type", "")
    if order_type != "subcontracting":
        return
    order_code = kwargs.get("order_code", "")
    material_code = kwargs.get("material_code", "")
    material_name = kwargs.get("material_name", "")
    plan_quantity = kwargs.get("plan_quantity", 0)
    supplier_code = kwargs.get("supplier_code", "")
    supplier_name = kwargs.get("supplier_name", "")
    source_mps_code = kwargs.get("source_mps_code", "")

    if not supplier_code:
        logger.warning(f"委外计划订单 {order_code} 未指定供应商，跳过自动创建委外工单")
        return

    try:
        order = await SubcontractingOrderService.create_order({
            "product_code": material_code,
            "product_name": material_name,
            "plan_quantity": plan_quantity,
            "supplier_code": supplier_code,
            "supplier_name": supplier_name,
            "source_planned_order_code": order_code,
            "source_mps_code": source_mps_code,
        })

        from base.plugins.mrp2.models.mrp_models import PlannedOrder
        po = await PlannedOrder.filter(order_code=order_code).first()
        if po:
            po.converted_sc_code = order.sc_code
            await po.save()

        logger.info(f"委外计划订单 {order_code} 自动创建委外工单: {order.sc_code}")
    except Exception as e:
        logger.error(f"委外计划订单 {order_code} 自动创建委外工单失败: {e}", exc_info=True)


async def on_inventory_picking_done(event_name: str = "", **kwargs):
    origin_type = kwargs.get("origin_type", "")
    if origin_type != "SC":
        return
    logger.info(f"委外库存出库完成事件: {kwargs}")


async def on_inventory_receipt_done(event_name: str = "", **kwargs):
    origin_type = kwargs.get("origin_type", "")
    if origin_type != "SC":
        return
    logger.info(f"委外库存入库完成事件: {kwargs}")


def register_event_handlers():
    if event_bus:
        event_bus.subscribe("mrp2.planned_order_confirmed", on_planned_order_confirmed)
        event_bus.subscribe("inventory.picking_done", on_inventory_picking_done)
        event_bus.subscribe("inventory.receipt_done", on_inventory_receipt_done)
        logger.info("委外事件处理器注册完成")