"""
大模型管理插件

支持多厂商大模型API接入和转发
"""
from fastapi import FastAPI
from base.common.log import log


# 导出包含所有API路由的主路由
try:
    from base.plugins.llm.api.v1 import api_router
    llm_router = api_router
except ImportError:
    llm_router = None
    log.warning("api_router模块未找到")


async def on_enable(app: FastAPI) -> bool:
    """插件启用时的钩子"""
    log.info("大模型管理插件正在启用...")
    # TODO: 初始化插件所需的资源
    return True


async def on_disable() -> bool:
    """插件禁用时的钩子"""
    log.info("大模型管理插件正在禁用...")
    # TODO: 清理插件资源
    return True


async def on_startup() -> None:
    """应用启动时的钩子"""
    log.info("大模型管理插件启动")
    # TODO: 执行启动时需要初始化的操作


async def on_shutdown() -> None:
    """应用关闭时的钩子"""
    log.info("大模型管理插件关闭")
    # TODO: 执行关闭时需要清理的操作


__all__ = ["on_enable", "on_disable", "on_startup", "on_shutdown", "llm_router"]
