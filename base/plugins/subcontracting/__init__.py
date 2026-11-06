from fastapi import FastAPI
from base.common.log import log

try:
    from base.plugins.subcontracting.api.v1 import subcontracting_api_router
    subcontracting_router = subcontracting_api_router
except ImportError:
    subcontracting_router = None
    log.warning("subcontracting_api_router模块未找到")

async def on_enable(app: FastAPI) -> bool:
    log.info("委外管理插件正在启用...")
    return True

async def on_disable() -> bool:
    log.info("委外管理插件正在禁用...")
    return True

async def on_startup() -> None:
    log.info("委外管理插件启动")
    try:
        from base.plugins.subcontracting.services.event_handlers import register_event_handlers
        register_event_handlers()
    except Exception as e:
        log.warning(f"委外事件处理器注册失败: {e}")
    try:
        from base.plugins.subcontracting.services.init_data import init_subcontracting_data
        await init_subcontracting_data()
    except Exception as e:
        log.warning(f"委外初始化数据失败: {e}")

async def on_shutdown() -> None:
    log.info("委外管理插件关闭")

__version__ = "1.0.0"
__plugin_name__ = "subcontracting"
__all__ = ["on_enable", "on_disable", "on_startup", "on_shutdown", "subcontracting_router"]