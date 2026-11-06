from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse
from base.plugins.finance.schemas.finance_schema import (
    JournalEntryCreate, JournalEntryUpdate, JournalEntryOut, JournalEntryListResponse
)
from base.plugins.finance.services.journal_service import JournalService

journal_router = APIRouter(prefix="/journals", tags=["凭证管理"])


@journal_router.get("/", summary="获取凭证列表")
async def get_journals(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    journal_type: Optional[str] = Query(None, description="凭证类型"),
    status: Optional[str] = Query(None, description="凭证状态"),
    period: Optional[str] = Query(None, description="会计期间"),
    journal_date_start: Optional[str] = Query(None, description="开始日期"),
    journal_date_end: Optional[str] = Query(None, description="结束日期"),
    keyword: Optional[str] = Query(None, description="搜索关键词")
):
    journals = await JournalService.get_all_journals(
        page, page_size, journal_type, status, period, journal_date_start, journal_date_end, keyword
    )
    total = await JournalService.get_journal_count(
        journal_type, status, period, journal_date_start, journal_date_end, keyword
    )
    
    data = [await journal.to_dict() for journal in journals]
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data
    })


@journal_router.get("/types", summary="获取凭证类型列表")
async def get_journal_types():
    types = await JournalService.get_journal_types()
    return SuccessResponse(data=types)


@journal_router.get("/statuses", summary="获取凭证状态列表")
async def get_journal_statuses():
    statuses = await JournalService.get_journal_statuses()
    return SuccessResponse(data=statuses)


@journal_router.get("/{journal_id}", response_model=JournalEntryOut, summary="获取凭证详情")
async def get_journal(journal_id: int):
    journal = await JournalService.get_journal_by_id(journal_id)
    if not journal:
        raise HTTPException(status_code=404, detail="凭证不存在")
    
    return await journal.to_dict()


@journal_router.post("/", response_model=JournalEntryOut, summary="创建凭证")
async def create_journal(journal_create: JournalEntryCreate):
    try:
        journal = await JournalService.create_journal(journal_create.model_dump())
        return await journal.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@journal_router.put("/{journal_id}", response_model=JournalEntryOut, summary="更新凭证")
async def update_journal(journal_id: int, journal_update: JournalEntryUpdate):
    try:
        journal = await JournalService.update_journal(journal_id, journal_update.model_dump(exclude_unset=True))
        if not journal:
            raise HTTPException(status_code=404, detail="凭证不存在")
        return await journal.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@journal_router.post("/{journal_id}/confirm", summary="审核凭证")
async def confirm_journal(journal_id: int, confirmed_by: Optional[str] = Query(None, description="审核人")):
    try:
        success = await JournalService.confirm_journal(journal_id, confirmed_by)
        if not success:
            raise HTTPException(status_code=404, detail="凭证不存在")
        return SuccessResponse(msg="审核成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@journal_router.post("/{journal_id}/post", summary="过账凭证")
async def post_journal(journal_id: int, posted_by: Optional[str] = Query(None, description="过账人")):
    try:
        success = await JournalService.post_journal(journal_id, posted_by)
        if not success:
            raise HTTPException(status_code=404, detail="凭证不存在")
        return SuccessResponse(msg="过账成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@journal_router.post("/{journal_id}/cancel", summary="取消凭证")
async def cancel_journal(journal_id: int, cancelled_by: Optional[str] = Query(None, description="取消人")):
    try:
        success = await JournalService.cancel_journal(journal_id, cancelled_by)
        if not success:
            raise HTTPException(status_code=404, detail="凭证不存在")
        return SuccessResponse(msg="取消成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))