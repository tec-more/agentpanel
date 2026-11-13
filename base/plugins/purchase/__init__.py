from fastapi import FastAPI
from base.common.log import log


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

__all__ = ["on_enable", "on_disable", "on_startup", "on_shutdown"]