"""
操作日志API
"""
from fastapi import APIRouter, Depends, status, Query
from typing import Optional
from datetime import datetime

from base.core.users.schemas.operation_log import OperationLogResponse
from base.core.users.services.operation_log_service import OperationLogService
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

router = APIRouter(prefix="/v1/logs", tags=["操作日志"])


@router.get("/list", summary="获取操作日志列表")
async def get_log_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量"),
        username: Optional[str] = Query(None, description="用户名(模糊搜索)"),
        module: Optional[str] = Query(None, description="操作模块"),
        operation: Optional[str] = Query(None, description="操作类型(模糊搜索)"),
        start_time: Optional[datetime] = Query(None, description="开始时间"),
        end_time: Optional[datetime] = Query(None, description="结束时间"),
        current_user_id: int = Depends(get_current_user_id)
):
    """获取操作日志列表(管理员功能)"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    logs, total = await OperationLogService.get_log_list(
        page=page,
        page_size=page_size,
        username=username,
        module=module,
        operation=operation,
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
        "items": log_list
    }

    return SuccessResponse(data=response_data)


# 清理保留天数的最小值：低于该值会误删近期操作日志
MIN_RETENTION_DAYS = 30


@router.delete("/cleanup", summary="清理旧日志")
async def cleanup_old_logs(
        days: int = Query(30, description=f"保留最近多少天的日志，最小 {MIN_RETENTION_DAYS} 天"),
        current_user_id: int = Depends(get_current_user_id)
):
    """清理指定天数前的日志(管理员功能)"""
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    if days < MIN_RETENTION_DAYS:
        return ErrorResponse(
            msg=f"保留天数最小为 {MIN_RETENTION_DAYS} 天（当前 {days} 天），过小会误删近期操作日志",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    deleted_count = await OperationLogService.delete_old_logs(days)

    return SuccessResponse(data={"deleted_count": deleted_count}, msg=f"已清理{deleted_count}条日志")
