from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

asset_disposal_router = APIRouter(prefix="/asset-disposal", tags=["资产清理"])


@asset_disposal_router.get("/", summary="获取资产清理列表")
async def get_asset_disposal(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    asset_code: Optional[str] = Query(None, description="资产编号"),
    asset_name: Optional[str] = Query(None, description="资产名称"),
    disposal_type: Optional[str] = Query(None, description="处置方式"),
    disposal_date: Optional[str] = Query(None, description="处置日期")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@asset_disposal_router.post("/", summary="新增资产清理")
async def create_asset_disposal():
    return SuccessResponse(msg="新增成功")


@asset_disposal_router.put("/", summary="更新资产清理")
async def update_asset_disposal():
    return SuccessResponse(msg="更新成功")


@asset_disposal_router.get("/{disposal_id}", summary="获取资产清理详情")
async def get_asset_disposal_detail(disposal_id: int):
    return SuccessResponse(data={
        "id": disposal_id,
        "asset_code": "",
        "asset_name": "",
        "disposal_type": "",
        "disposal_date": "",
        "original_value": 0,
        "accumulated_depreciation": 0,
        "net_value": 0,
        "disposal_amount": 0,
        "disposal_expense": 0,
        "disposal_result": "profit",
        "disposal_reason": "",
        "operator": ""
    })
