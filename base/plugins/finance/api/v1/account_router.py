from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse
from base.plugins.finance.schemas.finance_schema import AccountCreate, AccountUpdate, AccountOut, AccountListResponse
from base.plugins.finance.services.account_service import AccountService

account_router = APIRouter(prefix="/accounts", tags=["会计科目"])


@account_router.get("/", summary="获取会计科目列表")
async def get_accounts(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    account_type: Optional[str] = Query(None, description="科目类型"),
    keyword: Optional[str] = Query(None, description="搜索关键词")
):
    accounts = await AccountService.get_all_accounts(page, page_size, account_type, keyword)
    total = await AccountService.get_account_count(account_type, keyword)
    
    data = [await account.to_dict() for account in accounts]
    
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data
    })


@account_router.get("/tree", summary="获取会计科目树")
async def get_account_tree():
    tree = await AccountService.get_account_tree()
    return SuccessResponse(data=tree)


@account_router.get("/types", summary="获取科目类型列表")
async def get_account_types():
    types = await AccountService.get_account_types()
    return SuccessResponse(data=types)


@account_router.get("/{account_id}", response_model=AccountOut, summary="获取会计科目详情")
async def get_account(account_id: int):
    account = await AccountService.get_account_by_id(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="科目不存在")
    
    return await account.to_dict()


@account_router.post("/", response_model=AccountOut, summary="创建会计科目")
async def create_account(account_create: AccountCreate):
    try:
        existing = await AccountService.get_account_by_code(account_create.code)
        if existing:
            raise ValueError("科目编码已存在")
        
        account = await AccountService.create_account(account_create.model_dump())
        return await account.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@account_router.put("/{account_id}", response_model=AccountOut, summary="更新会计科目")
async def update_account(account_id: int, account_update: AccountUpdate):
    try:
        account = await AccountService.update_account(account_id, account_update.model_dump(exclude_unset=True))
        if not account:
            raise HTTPException(status_code=404, detail="科目不存在")
        return await account.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@account_router.delete("/{account_id}", summary="删除会计科目")
async def delete_account(account_id: int):
    try:
        success = await AccountService.delete_account(account_id)
        if not success:
            raise HTTPException(status_code=404, detail="科目不存在")
        return SuccessResponse(msg="删除成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@account_router.post("/initialize", summary="初始化默认会计科目")
async def initialize_accounts():
    try:
        await AccountService.initialize_default_accounts()
        return SuccessResponse(msg="初始化成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))