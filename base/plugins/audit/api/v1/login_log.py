from fastapi import APIRouter, Depends, Query, status
from typing import Optional
from datetime import datetime

from base.plugins.audit.schemas.audit_log import LoginLogResponse, LoginLogQuery
from base.plugins.audit.services.login_log_service import LoginLogService
from base.plugins.audit.services.data_change_service import MIN_RETENTION_DAYS
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

login_log_router = APIRouter(prefix="/login-logs", tags=["登录日志"])

@login_log_router.get("/list")
async def get_login_log_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    username: Optional[str] = Query(None, description="用户名"),
    login_type: Optional[str] = Query(None, description="登录类型"),
    login_method: Optional[str] = Query(None, description="登录方式"),
    success: Optional[bool] = Query(None, description="是否成功"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    ip_address: Optional[str] = Query(None, description="IP地址"),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取登录日志列表"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    logs, total = await LoginLogService.get_log_list(
        page=page,
        page_size=page_size,
        username=username,
        login_type=login_type,
        login_method=login_method,
        success=success,
        start_time=start_time,
        end_time=end_time,
        ip_address=ip_address,
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


@login_log_router.get("/{log_id}")
async def get_login_log(
    log_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """获取登录日志详情"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    log = await LoginLogService.get_log_by_id(log_id)
    if not log:
        return ErrorResponse(msg="登录日志不存在", status_code=status.HTTP_404_NOT_FOUND)

    log_dict = await log.to_dict()
    return SuccessResponse(data=log_dict)


@login_log_router.get("/user/{user_id}/history")
async def get_user_login_history(
    user_id: int,
    limit: int = Query(50, ge=1, le=200, description="数量限制"),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取用户登录历史"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not (current_user.is_superuser or current_user.id == user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    logs = await LoginLogService.get_user_login_history(user_id, limit)
    log_list = []
    for log in logs:
        log_dict = await log.to_dict()
        log_list.append(log_dict)

    return SuccessResponse(data={"items": log_list})


@login_log_router.get("/statistics/overview")
async def get_login_statistics(
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取登录统计信息"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    statistics = await LoginLogService.get_login_statistics(start_time=start_time, end_time=end_time)
    return SuccessResponse(data=statistics)


@login_log_router.delete("/cleanup")
async def cleanup_old_logs(
    days: int = Query(90, description=f"保留天数，最小 {MIN_RETENTION_DAYS} 天"),
    current_user_id: int = Depends(get_current_user_id),
):
    """清理旧登录日志"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    if days < MIN_RETENTION_DAYS:
        return ErrorResponse(
            msg=f"保留天数最小为 {MIN_RETENTION_DAYS} 天（当前 {days} 天），过小会误删近期审计数据",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    deleted_count = await LoginLogService.delete_old_logs(days)
    return SuccessResponse(data={"deleted_count": deleted_count}, msg=f"已清理 {deleted_count} 条旧日志")
