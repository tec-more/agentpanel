from fastapi import APIRouter, Depends, Query, status
from typing import Optional
from datetime import datetime

from base.plugins.audit.schemas.audit_log import DataChangeLogResponse, DataChangeLogQuery
from base.plugins.audit.services.data_change_service import (
    DataChangeService,
    MIN_RETENTION_DAYS,
)
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

data_change_log_router = APIRouter(prefix="/data-changes", tags=["数据变更日志"])

@data_change_log_router.get("/list")
async def get_data_change_log_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    table_name: Optional[str] = Query(None, description="表名"),
    record_id: Optional[str] = Query(None, description="记录ID"),
    change_type: Optional[str] = Query(None, description="变更类型"),
    username: Optional[str] = Query(None, description="用户名"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取数据变更日志列表"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    logs, total = await DataChangeService.get_log_list(
        page=page,
        page_size=page_size,
        table_name=table_name,
        record_id=record_id,
        change_type=change_type,
        username=username,
        start_time=start_time,
        end_time=end_time,
    )

    log_list = []
    for log in logs:
        log_dict = await log.to_dict()
        log_list.append(log_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": log_list,
    }

    return SuccessResponse(data=response_data)


@data_change_log_router.get("/{log_id}")
async def get_data_change_log(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """获取数据变更日志详情"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    log = await DataChangeService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="数据变更日志不存在", status_code=status.HTTP_404_NOT_FOUND)

    log_dict = await log.to_dict()
    return SuccessResponse(data=log_dict)


@data_change_log_router.get("/record/{table_name}/{record_id}")
async def get_record_changes(
    table_name: str,
    record_id: str,
    current_user_id: int = Depends(get_current_user_id),
):
    """获取某条记录的所有变更历史"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    logs = await DataChangeService.get_changes_by_record(table_name, record_id)
    log_list = []
    for log in logs:
        log_dict = await log.to_dict()
        log_list.append(log_dict)

    return SuccessResponse(data={"items": log_list})


@data_change_log_router.delete("/cleanup")
async def cleanup_old_logs(
    days: int = Query(90, description=f"保留天数，最小 {MIN_RETENTION_DAYS} 天"),
    current_user_id: int = Depends(get_current_user_id),
):
    """清理旧数据变更日志（授权类表不在清理范围内）"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    if days < MIN_RETENTION_DAYS:
        return ErrorResponse(
            msg=f"保留天数最小为 {MIN_RETENTION_DAYS} 天（当前 {days} 天），过小会误删近期审计数据",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    deleted_count = await DataChangeService.delete_old_logs(days)
    return SuccessResponse(data={"deleted_count": deleted_count}, msg=f"已清理 {deleted_count} 条旧日志")
