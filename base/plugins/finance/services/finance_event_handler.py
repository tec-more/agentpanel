import logging
from typing import Dict, Any

from base.common.events.event_bus import event_bus

try:
    from base.plugins.finance.services.finance_integration_service import FinanceIntegrationService
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)


async def on_purchase_confirmed(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_purchase_confirmed(kwargs)
    except Exception as e:
        logger.error(f"财务集成-采购确认处理失败: {e}", exc_info=True)


async def on_purchase_received(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_purchase_received(kwargs)
    except Exception as e:
        logger.error(f"财务集成-采购收货处理失败: {e}", exc_info=True)


async def on_purchase_payment(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_purchase_payment(kwargs)
    except Exception as e:
        logger.error(f"财务集成-采购付款处理失败: {e}", exc_info=True)


async def on_sales_paid(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_sales_paid(kwargs)
    except Exception as e:
        logger.error(f"财务集成-销售确认处理失败: {e}", exc_info=True)


async def on_sales_receipt(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_sales_receipt(kwargs)
    except Exception as e:
        logger.error(f"财务集成-销售收款处理失败: {e}", exc_info=True)


async def on_work_order_completed(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_work_order_completed(kwargs)
    except Exception as e:
        logger.error(f"财务集成-工单完工处理失败: {e}", exc_info=True)


async def on_material_picked(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_material_picked(kwargs)
    except Exception as e:
        logger.error(f"财务集成-领料处理失败: {e}", exc_info=True)


async def on_production_receipt(event_name: str, **kwargs):
    if not FINANCE_AVAILABLE:
        return
    try:
        await FinanceIntegrationService.on_production_receipt(kwargs)
    except Exception as e:
        logger.error(f"财务集成-生产入库处理失败: {e}", exc_info=True)


_FINANCE_HANDLERS = {
    "purchase.confirmed": on_purchase_confirmed,
    "purchase.received": on_purchase_received,
    "purchase.payment": on_purchase_payment,
    "sales.paid": on_sales_paid,
    "sales.receipt": on_sales_receipt,
    "work_order.completed": on_work_order_completed,
    "material.picked": on_material_picked,
    "production.receipt": on_production_receipt,
}
_registered = False


def register_finance_event_handlers():
    """注册财务集成订阅（幂等，由 manifest.events.register_ref 驱动）。"""
    global _registered
    if _registered:
        return
    for event_name, handler in _FINANCE_HANDLERS.items():
        event_bus.subscribe(event_name, handler)
    _registered = True
    logger.info("财务集成事件处理器注册完成")


def unregister_finance_event_handlers():
    """注销财务集成订阅，与插件停用对称。"""
    global _registered
    if not _registered:
        return
    for event_name, handler in _FINANCE_HANDLERS.items():
        event_bus.unsubscribe(event_name, handler)
    _registered = False
    logger.info("财务集成事件处理器已注销")