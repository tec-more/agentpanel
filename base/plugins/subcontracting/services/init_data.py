from loguru import logger


async def init_subcontracting_data():
    try:
        from base.plugins.inventory.models.inventory_models import StockPickingType
        existing = await StockPickingType.filter(picking_type_code="subcontracting_issue").first()
        if not existing:
            await StockPickingType.create(
                picking_type_code="subcontracting_issue",
                picking_type_name="委外发料",
                code="outgoing",
                sequence_code="SCI/{year}/{month}",
                is_active=True,
            )
            logger.info("初始化委外发料调拨类型")

        existing = await StockPickingType.filter(picking_type_code="subcontracting_receipt").first()
        if not existing:
            await StockPickingType.create(
                picking_type_code="subcontracting_receipt",
                picking_type_name="委外收货",
                code="incoming",
                sequence_code="SCR/{year}/{month}",
                is_active=True,
            )
            logger.info("初始化委外收货调拨类型")
    except Exception as e:
        logger.warning(f"初始化委外调拨类型失败(可能库存模块未安装): {e}")