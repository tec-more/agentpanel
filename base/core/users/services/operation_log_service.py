"""
操作日志服务
"""
from typing import List, Tuple, Optional
from datetime import datetime
from base.core.users.models.operation_log import OperationLog


class OperationLogService:
    """操作日志服务类"""

    @staticmethod
    async def create_log(
            user_id: Optional[int],
            username: Optional[str],
            module: Optional[str],
            operation: str,
            method: str,
            path: str,
            ip_address: Optional[str],
            user_agent: Optional[str],
            request_params: Optional[dict],
            response_data: Optional[str],
            status_code: Optional[int],
            error_message: Optional[str],
            duration: Optional[int]
    ) -> OperationLog:
        """创建操作日志"""
        log = await OperationLog.create(
            user_id=user_id,
            username=username,
            module=module,
            operation=operation,
            method=method,
            path=path,
            ip_address=ip_address,
            user_agent=user_agent,
            request_params=request_params,
            response_data=response_data,
            status_code=status_code,
            error_message=error_message,
            duration=duration
        )
        return log

    @staticmethod
    async def get_log_list(
            page: int = 1,
            page_size: int = 10,
            username: Optional[str] = None,
            module: Optional[str] = None,
            operation: Optional[str] = None,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> Tuple[List[OperationLog], int]:
        """获取操作日志列表"""
        query = OperationLog.all()

        if username:
            query = query.filter(username__icontains=username)
        if module:
            query = query.filter(module=module)
        if operation:
            query = query.filter(operation__icontains=operation)
        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)

        total = await query.count()

        offset = (page - 1) * page_size
        logs = await query.offset(offset).limit(page_size).order_by('-created_at')

        return logs, total

    @staticmethod
    async def delete_old_logs(days: int = 30) -> int:
        """删除指定天数前的日志"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = await OperationLog.filter(created_at__lt=cutoff_date).delete()
        return deleted_count
