from fastapi import APIRouter
from base.plugins.sales.api.v1.order_router import order_router
from base.plugins.sales.api.v1.stats_router import stats_router

sales_v1_router = APIRouter()

sales_v1_router.include_router(order_router, prefix="", tags=["订单管理"])
sales_v1_router.include_router(stats_router, prefix="", tags=["销售统计"])
