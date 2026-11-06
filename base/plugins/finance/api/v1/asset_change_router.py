from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

asset_change_router = APIRouter(prefix="/asset-change", tags=["资产变动"])


@asset_change_router.get("/", summary="获取资产变动列表")
async def get_asset_change(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    asset_code: Optional[str] = Query(None, description="资产编号"),
    asset_name: Optional[str] = Query(None, description="资产名称"),
    change_type: Optional[str] = Query(None, description="变动类型"),
    change_date: Optional[str] = Query(None, description="变动日期")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@asset_change_router.post("/", summary="新增资产变动")
async def create_asset_change():
    return SuccessResponse(msg="新增成功")


@asset_change_router.put("/", summary="更新资产变动")
async def update_asset_change():
    return SuccessResponse(msg="更新成功")


@asset_change_router.get("/{change_id}", summary="获取资产变动详情")
async def get_asset_change_detail(change_id: int):
    return SuccessResponse(data={
        "id": change_id,
        "asset_code": "",
        "asset_name": "",
        "change_type": "",
        "change_date": "",
        "before_value": "",
        "after_value": "",
        "change_reason": "",
        "operator": ""
    })
