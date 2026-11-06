"""
审批模块 - Approval Plugin
提供通用审批流程配置、多级审批引擎、全局审批拦截等功能
"""
from loguru import logger


async def on_enable(app):
    logger.info("审批插件启用，初始化默认数据...")
    from base.plugins.approval.services.flow_service import FlowService
    await FlowService.initialize_default_data()
    logger.info("审批插件默认数据初始化完成")
    return True


async def on_disable():
    logger.info("审批插件禁用...")


async def on_startup():
    logger.info("审批插件启动，注册全局中间件...")
    # 中间件在 start.py 中注册，这里不做操作
    logger.info("审批插件启动完成")


async def on_shutdown():
    logger.info("审批插件关闭...")
