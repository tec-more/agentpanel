"""
消息模块 - Mail Plugin
仿 Odoo mail 机制，提供记录消息（Chatter）、关注者、通知功能
通过订阅 audit 的 model.* 事件自动产生系统消息
"""
from loguru import logger


async def on_enable(app):
    logger.info("消息插件启用，初始化默认数据...")
    from base.plugins.mail.services.subtype_service import SubtypeService
    from base.plugins.mail.services.mapping_service import MappingService
    from base.plugins.mail.services.event_handler import register_mail_event_handlers

    await SubtypeService.initialize_default_data()
    await MappingService.initialize_default_data()
    register_mail_event_handlers()
    logger.info("消息插件初始化完成（默认子类型 + 默认映射 + 事件订阅）")
    return True


async def on_disable():
    logger.info("消息插件禁用，注销事件订阅...")
    from base.plugins.mail.services.event_handler import unregister_mail_event_handlers
    unregister_mail_event_handlers()
    logger.info("消息插件已禁用")


async def on_startup():
    logger.info("消息插件启动，重新注册事件订阅...")
    # 进程重启后 event_bus 订阅会丢失，需在 startup 时重新注册
    from base.plugins.mail.services.event_handler import register_mail_event_handlers
    register_mail_event_handlers()
    logger.info("消息插件启动完成")


async def on_shutdown():
    logger.info("消息插件关闭...")
    from base.plugins.mail.services.event_handler import unregister_mail_event_handlers
    unregister_mail_event_handlers()
