"""
第三方平台API接口
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from base.common.response import SuccessResponse
from base.common.security import get_current_user_id
from base.plugins.thirdparty.schemas.platform import PlatformCreate, PlatformUpdate, PlatformResponse
from base.plugins.thirdparty.services.platform_service import PlatformService

platform_router = APIRouter(prefix="/platforms", tags=["第三方平台"])


@platform_router.post("/", response_model=PlatformResponse)
async def create_platform(
    platform_data: PlatformCreate,
    current_user_id: int = Depends(get_current_user_id)
):
    """创建第三方平台"""
    platform = await PlatformService.create_platform(platform_data)
    return SuccessResponse(data=platform)


@platform_router.get("/", response_model=List[PlatformResponse])
async def get_platforms(
    skip: int = 0,
    limit: int = 100,
    current_user_id: int = Depends(get_current_user_id)
):
    """获取第三方平台列表"""
    platforms = await PlatformService.get_platforms(skip, limit)
    return SuccessResponse(data=platforms)


@platform_router.get("/{platform_id}", response_model=PlatformResponse)
async def get_platform(
    platform_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """获取第三方平台详情"""
    platform = await PlatformService.get_platform_by_id(platform_id)
    if not platform:
        raise HTTPException(status_code=404, detail="平台不存在")
    return SuccessResponse(data=platform)


@platform_router.put("/{platform_id}", response_model=PlatformResponse)
async def update_platform(
    platform_id: int,
    platform_data: PlatformUpdate,
    current_user_id: int = Depends(get_current_user_id)
):
    """更新第三方平台"""
    platform = await PlatformService.update_platform(platform_id, platform_data)
    if not platform:
        raise HTTPException(status_code=404, detail="平台不存在")
    return SuccessResponse(data=platform)


@platform_router.delete("/{platform_id}")
async def delete_platform(
    platform_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """删除第三方平台"""
    success = await PlatformService.delete_platform(platform_id)
    if not success:
        raise HTTPException(status_code=404, detail="平台不存在")
    return SuccessResponse(msg="平台删除成功")


@platform_router.post("/{platform_id}/test")
async def test_platform_connection(
    platform_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """测试平台连接"""
    success = await PlatformService.test_platform_connection(platform_id)
    if not success:
        raise HTTPException(status_code=404, detail="平台不存在")
    return SuccessResponse(data={"connected": success}, msg="连接测试成功")