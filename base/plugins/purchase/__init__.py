from fastapi import FastAPI
from base.common.log import log

try:
    from base.plugins.purchase.api.v1 import purchase_api_router
    purchase_router = purchase_api_router
except ImportError:
    purchase_router = None
    log.warning("purchase_api_router模块未找到")


async def on_enable(app: FastAPI) -> bool:
    log.info("采购管理插件正在启用...")
    return True


async def on_disable() -> bool:
    log.info("采购管理插件正在禁用...")
    return True


async def on_startup() -> None:
    log.info("采购管理插件启动")


async def on_shutdown() -> None:
    log.info("采购管理插件关闭")


__version__ = "1.0.0"
__plugin_name__ = "purchase"

__all__ = ["on_enable", "on_disable", "on_startup", "on_shutdown", "purchase_router"]