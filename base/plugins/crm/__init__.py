"""
CRM Plugin - CRM模块
提供线索管理、商机管理、活动管理、联系人管理、跟进任务管理、统计分析等功能
"""
from loguru import logger


async def on_enable(app):
    logger.info("CRM插件启用，初始化默认数据...")
    from base.plugins.crm.services.crm_config_service import CrmConfigService
    await CrmConfigService.initialize_default_data()
    logger.info("CRM插件默认数据初始化完成")
    return True


async def on_disable():
    logger.info("CRM插件禁用，清理定时任务...")


async def on_startup():
    logger.info("CRM插件启动，注册事件订阅和定时任务...")
    from base.common.events.event_bus import event_bus
    from base.plugins.crm.services.crm_scheduler_service import CrmSchedulerService
    event_bus.subscribe("sales.paid", CrmSchedulerService.handle_order_paid)
    logger.info("CRM插件启动完成")


async def on_shutdown():
    logger.info("CRM插件关闭，取消事件订阅和定时任务...")
    from base.common.events.event_bus import event_bus
    from base.plugins.crm.services.crm_scheduler_service import CrmSchedulerService
    event_bus.unsubscribe("sales.paid", CrmSchedulerService.handle_order_paid)
    logger.info("CRM插件关闭完成")