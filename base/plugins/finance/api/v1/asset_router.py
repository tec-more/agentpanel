from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse

asset_router = APIRouter(prefix="/assets", tags=["资产管理"])


@asset_router.get("/", summary="获取资产列表")
async def get_assets(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    asset_type: Optional[str] = Query(None, description="资产类型"),
    department_id: Optional[int] = Query(None, description="部门ID"),
    status: Optional[str] = Query(None, description="状态"),
    keyword: Optional[str] = Query(None, description="搜索关键词")
):
    return SuccessResponse(data={
        "total": 0,
        "page": page,
        "page_size": page_size,
        "data": []
    })


@asset_router.get("/{asset_id}", summary="获取资产详情")
async def get_asset(asset_id: int):
    return SuccessResponse(data={"id": asset_id, "detail": {}})


@asset_router.post("/", summary="创建资产")
async def create_asset():
    return SuccessResponse(data={"id": 1}, msg="创建成功")


@asset_router.put("/{asset_id}", summary="更新资产")
async def update_asset(asset_id: int):
    return SuccessResponse(data={"id": asset_id}, msg="更新成功")


@asset_router.post("/{asset_id}/depreciation", summary="计提折旧")
async def depreciate_asset(asset_id: int):
    return SuccessResponse(msg="折旧计提成功")


@asset_router.post("/{asset_id}/dispose", summary="资产清理")
async def dispose_asset(asset_id: int):
    return SuccessResponse(msg="资产清理成功")