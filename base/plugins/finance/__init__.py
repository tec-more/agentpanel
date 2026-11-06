from fastapi import FastAPI
from base.common.log import log

pass


async def on_enable(app: FastAPI) -> bool:
    log.info("财务管理插件正在启用...")
    return True


async def on_disable() -> bool:
    log.info("财务管理插件正在禁用...")
    return True


async def on_startup() -> None:
    log.info("财务管理插件启动")
    try:
        from base.plugins.finance.services.account_service import AccountService
        await AccountService.initialize_default_accounts()
        log.info("默认会计科目初始化完成")
    except Exception as e:
        log.warning(f"默认会计科目初始化失败: {e}")

    try:
        from base.plugins.finance.services.finance_event_handler import register_finance_event_handlers
        register_finance_event_handlers()
        log.info("财务集成事件处理器注册完成")
    except Exception as e:
        log.warning(f"财务集成事件处理器注册失败: {e}")

    try:
        from base.plugins.finance.services.integration_account_mapping_service import IntegrationAccountMappingService
        default_mappings = [
            {"event_type": "purchase_confirmed", "debit_account_code": "1401", "credit_account_code": "2202", "description": "采购确认-应付"},
            {"event_type": "purchase_received", "debit_account_code": "1403", "credit_account_code": "1401", "description": "采购入库-在途转库存"},
            {"event_type": "purchase_payment", "debit_account_code": "2202", "credit_account_code": "1002", "description": "采购付款-应付转银行"},
            {"event_type": "sales_paid", "debit_account_code": "1122", "credit_account_code": "6001", "description": "销售确认-应收转收入"},
            {"event_type": "sales_receipt", "debit_account_code": "1002", "credit_account_code": "1122", "description": "销售收款-银行转应收"},
            {"event_type": "work_order_completed", "debit_account_code": "1405", "credit_account_code": "5001", "description": "工单完工-生产成本转库存"},
            {"event_type": "material_picked", "debit_account_code": "5001", "credit_account_code": "1405", "description": "领料-库存转生产成本"},
            {"event_type": "production_receipt", "debit_account_code": "1405", "credit_account_code": "5001", "description": "生产入库-生产成本转库存"},
        ]
        for mapping_data in default_mappings:
            existing = await IntegrationAccountMappingService.get_mapping_by_event_type(mapping_data["event_type"])
            if not existing:
                await IntegrationAccountMappingService.create_mapping(mapping_data)
        log.info("默认科目映射初始化完成")
    except Exception as e:
        log.warning(f"默认科目映射初始化失败: {e}")


async def on_shutdown() -> None:
    log.info("财务管理插件关闭")


__version__ = "1.0.0"
__plugin_name__ = "finance"

__all__ = ["on_enable", "on_disable", "on_startup", "on_shutdown", "finance_router"]