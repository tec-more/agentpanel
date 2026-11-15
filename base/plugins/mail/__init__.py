"""
消息模块 - Mail Plugin
仿 Odoo mail 机制，提供记录消息（Chatter）、关注者、通知功能
通过订阅 audit 的 model.* 事件自动产生系统消息

事件订阅已统一到 ``task/subscriptions.py`` 的 ``@ap_subscribe`` 声明，由事件中心
按发现结果装卸；此处的生命周期钩子只负责默认数据初始化，不再手工注册/注销订阅。
"""
from loguru import logger


async def on_enable(app):
    logger.info("消息插件启用，初始化默认数据...")
    from base.plugins.mail.services.subtype_service import SubtypeService
    from base.plugins.mail.services.mapping_service import MappingService

    await SubtypeService.initialize_default_data()
    await MappingService.initialize_default_data()
    logger.info("消息插件初始化完成（默认子类型 + 默认映射；订阅由事件中心统一装卸）")
    return True


async def on_disable():
    logger.info("消息插件禁用（订阅注销由事件中心统一执行）")
    return True


async def on_startup():
    logger.info("消息插件启动（订阅由事件中心按 task/ 声明注册）")


async def on_shutdown():
    logger.info("消息插件关闭（订阅注销由事件中心统一执行）")
