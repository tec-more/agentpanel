"""
CRM Plugin - CRM模块
提供线索管理、商机管理、活动管理、联系人管理、跟进任务管理、统计分析等功能

事件订阅由 manifest.events 声明，事件中心在插件启用/禁用时调用下列函数，
不再依赖只在进程启动时触发的 on_startup 钩子。
"""
from loguru import logger

from base.common.events.event_bus import event_bus

_crm_handler = None
_registered = False


def register_crm_event_handlers():
    """注册 CRM 订阅（幂等）。"""
    global _crm_handler, _registered
    if _registered:
        return
    from base.plugins.crm.services.crm_scheduler_service import CrmSchedulerService

    _crm_handler = CrmSchedulerService.handle_order_paid
    event_bus.subscribe("sales.paid", _crm_handler)
    _registered = True
    logger.info("[crm] 声明订阅已注册: sales.paid")


def unregister_crm_event_handlers():
    """注销 CRM 订阅，与插件停用对称。"""
    global _registered
    if not _registered:
        return
    event_bus.unsubscribe("sales.paid", _crm_handler)
    _registered = False
    logger.info("[crm] 声明订阅已注销: sales.paid")


async def on_enable(app):
    logger.info("CRM插件启用，初始化默认数据...")
    from base.plugins.crm.services.crm_config_service import CrmConfigService
    await CrmConfigService.initialize_default_data()
    logger.info("CRM插件默认数据初始化完成")
    return True


async def on_disable():
    logger.info("CRM插件禁用（订阅注销由事件中心统一执行）")
    return True


async def on_startup():
    logger.info("CRM插件启动（订阅已由事件中心按 manifest 声明注册）")


async def on_shutdown():
    logger.info("CRM插件关闭（订阅注销由事件中心统一执行）")
