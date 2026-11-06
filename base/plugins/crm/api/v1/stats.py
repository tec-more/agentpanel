from fastapi import APIRouter
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.crm.services.crm_stats_service import CrmStatsService

stats_router = APIRouter(prefix="/stats", tags=["CRM统计分析"])


@stats_router.get("/funnel")
async def get_funnel_stats(
    user_id: int = require_permission("crm:stats:view"),
):
    result = await CrmStatsService.get_funnel_stats(user_id)
    return success_response(data=result.model_dump())


@stats_router.get("/lead-sources")
async def get_lead_source_stats(
    user_id: int = require_permission("crm:stats:view"),
):
    result = await CrmStatsService.get_lead_source_stats(user_id)
    return success_response(data=result.model_dump())


@stats_router.get("/sales-performance")
async def get_sales_performance(
    user_id: int = require_permission("crm:stats:view"),
):
    result = await CrmStatsService.get_sales_performance(user_id)
    return success_response(data=result.model_dump())


@stats_router.get("/customer-follow-up")
async def get_customer_follow_up(
    user_id: int = require_permission("crm:stats:view"),
):
    result = await CrmStatsService.get_customer_follow_up(user_id)
    return success_response(data=result.model_dump())