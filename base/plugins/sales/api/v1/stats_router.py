from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query
from decimal import Decimal

from base.common.response import SuccessResponse
from base.plugins.sales.services.sales_service import SalesService

stats_router = APIRouter(prefix="/stats", tags=["销售统计"])


@stats_router.get("/overview", summary="销售概览")
async def get_sales_overview(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD")
):
    stats = await SalesService.get_sales_overview(start_date, end_date)
    return SuccessResponse(data=stats, msg="获取销售概览成功")


@stats_router.get("/daily", summary="每日销售统计")
async def get_daily_sales(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    stats = await SalesService.get_daily_sales(start_date, end_date)
    return SuccessResponse(data=stats, msg="获取每日销售统计成功")


@stats_router.get("/monthly", summary="月度销售统计")
async def get_monthly_sales(
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份")
):
    stats = await SalesService.get_monthly_sales(year, month)
    return SuccessResponse(data=stats, msg="获取月度销售统计成功")


@stats_router.get("/top-products", summary="畅销产品排行")
async def get_top_products(
    limit: int = Query(10, ge=1, le=50, description="数量限制"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD")
):
    stats = await SalesService.get_top_products(limit, start_date, end_date)
    return SuccessResponse(data=stats, msg="获取畅销产品排行成功")


@stats_router.get("/top-customers", summary="客户消费排行")
async def get_top_customers(
    limit: int = Query(10, ge=1, le=50, description="数量限制"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD")
):
    stats = await SalesService.get_top_customers(limit, start_date, end_date)
    return SuccessResponse(data=stats, msg="获取客户消费排行成功")


@stats_router.get("/payment-methods", summary="支付方式统计")
async def get_payment_method_stats(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD")
):
    stats = await SalesService.get_payment_method_stats(start_date, end_date)
    return SuccessResponse(data=stats, msg="获取支付方式统计成功")
