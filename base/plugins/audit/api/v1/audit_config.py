from fastapi import APIRouter, Depends, Query, status
from typing import Optional

from base.plugins.audit.schemas.audit_log import (
    AuditConfigResponse,
    AuditConfigCreate,
    AuditConfigUpdate,
)
from base.plugins.audit.services.audit_config_service import AuditConfigService
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

audit_config_router = APIRouter(prefix="/audit-configs", tags=["审计配置"])

@audit_config_router.post("/")
async def create_audit_config(
    data: AuditConfigCreate,
    current_user_id: int = Depends(get_current_user_id),
):
    """创建审计配置"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    config = await AuditConfigService.get_config_by_module(data.module_name)
    if config:
        return ErrorResponse(msg="该模块的审计配置已存在", status_code=status.HTTP_400_BAD_REQUEST)

    config = await AuditConfigService.create_config(data)
    config_dict = await config.to_dict()
    return SuccessResponse(data=config_dict, msg="创建成功", status_code=status.HTTP_201_CREATED)


@audit_config_router.get("/list")
async def get_audit_config_list(
    current_user_id: int = Depends(get_current_user_id),
):
    """获取审计配置列表"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    configs = await AuditConfigService.get_all_configs()
    config_list = []
    for config in configs:
        config_dict = await config.to_dict()
        config_list.append(config_dict)

    return SuccessResponse(data={"items": config_list})


@audit_config_router.get("/{config_id}")
async def get_audit_config(
    config_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """获取审计配置详情"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    config = await AuditConfigService.get_config_by_id(config_id)
    if not config:
        return ErrorResponse(msg="审计配置不存在", status_code=status.HTTP_404_NOT_FOUND)

    config_dict = await config.to_dict()
    return SuccessResponse(data=config_dict)


@audit_config_router.get("/module/{module_name}")
async def get_audit_config_by_module(
    module_name: str,
    current_user_id: int = Depends(get_current_user_id),
):
    """根据模块名获取审计配置"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    config = await AuditConfigService.get_config_by_module(module_name)
    if not config:
        return ErrorResponse(msg="审计配置不存在", status_code=status.HTTP_404_NOT_FOUND)

    config_dict = await config.to_dict()
    return SuccessResponse(data=config_dict)


@audit_config_router.put("/{config_id}")
async def update_audit_config(
    config_id: int,
    data: AuditConfigUpdate,
    current_user_id: int = Depends(get_current_user_id),
):
    """更新审计配置"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    config = await AuditConfigService.update_config(config_id, data)
    if not config:
        return ErrorResponse(msg="审计配置不存在", status_code=status.HTTP_404_NOT_FOUND)

    config_dict = await config.to_dict()
    return SuccessResponse(data=config_dict, msg="更新成功")


@audit_config_router.delete("/{config_id}")
async def delete_audit_config(
    config_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """删除审计配置"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    success = await AuditConfigService.delete_config(config_id)
    if not success:
        return ErrorResponse(msg="审计配置不存在", status_code=status.HTTP_404_NOT_FOUND)

    return SuccessResponse(msg="删除成功")
