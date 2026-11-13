"""委外管理插件。

事件订阅由 manifest.events 声明，事件中心在插件启用/禁用时装卸，
不再只在进程启动时由 on_startup 注册。
"""
from fastapi import FastAPI

from base.common.log import log
from base.common.events.event_bus import event_bus

_registered = False


def register_event_handlers():
    """注册委外订阅（幂等）。"""
    global _registered
    if _registered:
        return
    from base.plugins.subcontracting.services.event_handlers import register_event_handlers as _reg
    _reg()
    _registered = True


def unregister_event_handlers():
    """注销委外订阅，与插件停用对称。"""
    global _registered
    if not _registered:
        return
    from base.plugins.subcontracting.services import event_handlers as handlers

    pairs = (
        ("mrp2.planned_order_confirmed", handlers.on_planned_order_confirmed),
        ("inventory.picking_done", handlers.on_inventory_picking_done),
        ("inventory.receipt_done", handlers.on_inventory_receipt_done),
    )
    for event_name, handler in pairs:
        event_bus.unsubscribe(event_name, handler)
    _registered = False
    log.info("[委外] 声明订阅已注销")


async def on_enable(app: FastAPI) -> bool:
    log.info("委外管理插件正在启用...")
    return True


async def on_disable() -> bool:
    log.info("委外管理插件正在禁用（订阅注销由事件中心统一执行）")
    return True


async def on_startup() -> None:
    log.info("委外管理插件启动（订阅已由事件中心按 manifest 声明注册）")
    try:
        from base.plugins.subcontracting.services.init_data import init_subcontracting_data
        await init_subcontracting_data()
    except Exception as e:
        log.warning(f"委外初始化数据失败: {e}")


async def on_shutdown() -> None:
    log.info("委外管理插件关闭")

__version__ = "1.0.0"
__plugin_name__ = "subcontracting"
__all__ = [
    "on_enable", "on_disable", "on_startup", "on_shutdown",
    "register_event_handlers", "unregister_event_handlers",
]
