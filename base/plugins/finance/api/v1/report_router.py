from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse
from base.plugins.finance.schemas.finance_schema import (
    DailyJournalListResponse, GeneralLedgerListResponse, TrialBalanceListResponse,
    ProfitLossReportOut, BalanceSheetReportOut, CashFlowReportOut
)
from base.plugins.finance.services.report_service import ReportService

report_router = APIRouter(prefix="/reports", tags=["财务报表"])


@report_router.get("/daily", summary="获取日记账列表")
async def get_daily_journal(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    journal_date_start: Optional[str] = Query(None, description="开始日期"),
    journal_date_end: Optional[str] = Query(None, description="结束日期"),
    account_id: Optional[int] = Query(None, description="科目ID"),
    period: Optional[str] = Query(None, description="会计期间")
):
    journals = await ReportService.get_daily_journal(page, page_size, journal_date_start, journal_date_end, account_id, period)
    total = await ReportService.get_daily_journal_count(journal_date_start, journal_date_end, account_id, period)
    
    data = [await journal.to_dict() for journal in journals]
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data
    })


@report_router.get("/ledger", summary="获取总账列表")
async def get_general_ledger(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    period: Optional[str] = Query(None, description="会计期间"),
    account_id: Optional[int] = Query(None, description="科目ID"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份")
):
    ledgers = await ReportService.get_general_ledger(page, page_size, period, account_id, year, month)
    total = await ReportService.get_general_ledger_count(period, account_id, year, month)
    
    data = [await ledger.to_dict() for ledger in ledgers]
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data
    })


@report_router.get("/trial_balance", summary="获取科目余额表")
async def get_trial_balance(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    period: Optional[str] = Query(None, description="会计期间"),
    account_type: Optional[str] = Query(None, description="科目类型"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份")
):
    balances = await ReportService.get_trial_balance(page, page_size, period, account_type, year, month)
    total = await ReportService.get_trial_balance_count(period, account_type, year, month)
    
    data = [await balance.to_dict() for balance in balances]
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data
    })


@report_router.post("/trial_balance/generate", summary="生成科目余额表")
async def generate_trial_balance(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份")
):
    try:
        data = await ReportService.generate_trial_balance(year, month)
        return SuccessResponse(data=data, msg="生成成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@report_router.get("/profit_loss", summary="获取利润表")
async def get_profit_loss_report(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份")
):
    try:
        data = await ReportService.generate_profit_loss_report(year, month)
        return SuccessResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@report_router.get("/balance_sheet", summary="获取资产负债表")
async def get_balance_sheet(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份")
):
    try:
        data = await ReportService.generate_balance_sheet(year, month)
        return SuccessResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@report_router.get("/cash_flow", summary="获取现金流量表")
async def get_cash_flow_report(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份")
):
    try:
        data = await ReportService.generate_cash_flow_report(year, month)
        return SuccessResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@report_router.post("/generate", summary="生成财务报表")
async def generate_financial_report(
    report_type: str = Query(..., description="报表类型(trial_balance/profit_loss/balance_sheet/cash_flow)"),
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份")
):
    try:
        data = await ReportService.generate_financial_report(report_type, year, month)
        return SuccessResponse(data=data, msg="生成成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))