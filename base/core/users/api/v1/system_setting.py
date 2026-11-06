"""
系统设置API
"""
from fastapi import APIRouter, Depends, status, Query
from typing import Optional

from base.core.users.schemas.system_setting import (
    SystemSettingResponse,
    SystemSettingCreate,
    SystemSettingUpdate,
    SystemSettingListResponse,
)
from base.core.users.services.system_setting_service import SystemSettingService
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

router = APIRouter(prefix="/v1/system-settings", tags=["系统设置"])


@router.get("/list", summary="获取系统设置列表(分页)")
async def get_system_setting_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(100, ge=1, le=200, description="每页数量"),
        key: Optional[str] = Query(None, description="设置键(模糊搜索)"),
        name: Optional[str] = Query(None, description="设置名称(模糊搜索)"),
        is_active: Optional[bool] = Query(None, description="是否激活"),
        current_user_id: int = Depends(get_current_user_id)
):
    """
    获取系统设置列表(分页)

    需要认证
    """
    settings, total = await SystemSettingService.get_setting_list(
        page=page,
        page_size=page_size,
        key=key,
        name=name,
        is_active=is_active,
    )

    setting_list = []
    for setting in settings:
        setting_dict = await setting.to_dict()
        setting_list.append(setting_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": setting_list
    }

    return SuccessResponse(data=response_data)


@router.get("/public", summary="获取公开的系统设置")
async def get_public_settings():
    """
    获取公开的系统设置（无需登录）
    """
    settings = await SystemSettingService.get_all_active_settings()
    return SuccessResponse(data=settings)


@router.post("", summary="创建系统设置")
async def create_system_setting(
        setting_data: SystemSettingCreate,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    创建系统设置(管理员功能)
    """
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    if await SystemSettingService.check_key_exists(setting_data.key):
        return ErrorResponse(
            msg="设置键已存在",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    setting = await SystemSettingService.create_setting(setting_data)
    setting_dict = await setting.to_dict()

    return SuccessResponse(data=setting_dict, msg="创建成功")


@router.put("/batch", summary="批量更新系统设置")
async def batch_update_system_settings(
        settings_data: dict,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    批量更新系统设置值（键值对形式）
    """
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    updated_settings = []
    for key, value in settings_data.items():
        setting = await SystemSettingService.update_setting_by_key(key, str(value))
        if setting:
            updated_settings.append(await setting.to_dict())

    return SuccessResponse(data=updated_settings, msg="批量更新成功")


@router.post("/init", summary="初始化默认设置")
async def init_default_settings(
        current_user_id: int = Depends(get_current_user_id)
):
    """
    初始化默认系统设置(管理员功能)
    """
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    await SystemSettingService.init_default_settings()
    return SuccessResponse(msg="初始化成功")


@router.get("/{setting_id}", summary="获取系统设置详情")
async def get_system_setting_detail(
        setting_id: int,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    获取系统设置详情

    Args:
        setting_id: 设置ID
        current_user_id: 当前用户ID

    Returns:
        设置详细信息
    """
    setting = await SystemSettingService.get_by_id(setting_id)
    if not setting:
        return ErrorResponse(
            msg="设置不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    setting_dict = await setting.to_dict()
    return SuccessResponse(data=setting_dict)


@router.put("/{setting_id}", summary="更新系统设置")
async def update_system_setting(
        setting_id: int,
        setting_data: SystemSettingUpdate,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    更新系统设置
    """
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    setting = await SystemSettingService.update_setting(setting_id, setting_data)
    if not setting:
        return ErrorResponse(
            msg="设置不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    setting_dict = await setting.to_dict()
    return SuccessResponse(data=setting_dict, msg="更新成功")


@router.delete("/{setting_id}", summary="删除系统设置")
async def delete_system_setting(
        setting_id: int,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    删除系统设置(管理员功能)
    """
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    success = await SystemSettingService.delete_setting(setting_id)
    if not success:
        return ErrorResponse(
            msg="设置不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    return SuccessResponse(msg="删除成功")
