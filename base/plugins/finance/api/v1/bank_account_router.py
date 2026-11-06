from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

bank_account_router = APIRouter(prefix="/bank-accounts", tags=["银行账户"])


@bank_account_router.get("/", summary="获取银行账户列表")
async def get_bank_accounts(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@bank_account_router.get("/{account_id}", summary="获取银行账户详情")
async def get_bank_account(account_id: int):
    return SuccessResponse(data={"id": account_id, "detail": {}})


@bank_account_router.post("/", summary="创建银行账户")
async def create_bank_account():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@bank_account_router.put("/{account_id}", summary="更新银行账户")
async def update_bank_account(account_id: int):
    return SuccessResponse(data={"id": account_id}, msg="更新成功")


@bank_account_router.delete("/{account_id}", summary="删除银行账户")
async def delete_bank_account(account_id: int):
    return SuccessResponse(msg="删除成功")