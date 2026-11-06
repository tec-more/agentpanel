from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
from base.plugins.audit.models.audit_log import LoginLog
from base.plugins.audit.schemas.audit_log import LoginLogCreate
class LoginLogService:
    model = "login_log"
    """登录日志服务"""

    @staticmethod
    async def create_log(data: LoginLogCreate) -> LoginLog:
        """创建登录日志"""
        if isinstance(data, dict):
            log = await LoginLog.create(**data)
        else:
            log = await LoginLog.create(**data.model_dump(exclude_unset=True))
        return log

    @staticmethod
    async def get_log_by_id(log_id: int) -> Optional[LoginLog]:
        """根据ID获取登录日志"""
        return await LoginLog.get_or_none(id=log_id)

    @staticmethod
    async def get_log_list(
        page: int = 1,
        page_size: int = 20,
        username: Optional[str] = None,
        login_type: Optional[str] = None,
        login_method: Optional[str] = None,
        success: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[List[LoginLog], int]:
        """获取登录日志列表"""
        query = LoginLog.all()

        if username:
            query = query.filter(username__icontains=username)
        if login_type:
            query = query.filter(login_type=login_type)
        if login_method:
            query = query.filter(login_method=login_method)
        if success is not None:
            query = query.filter(success=success)
        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)
        if ip_address:
            query = query.filter(ip_address__icontains=ip_address)

        total = await query.count()
        offset = (page - 1) * page_size
        logs = await query.offset(offset).limit(page_size).order_by("-created_at")

        return logs, total

    @staticmethod
    async def get_user_login_history(user_id: int, limit: int = 50) -> List[LoginLog]:
        """获取用户登录历史"""
        logs = await LoginLog.filter(user_id=user_id).limit(limit).order_by("-created_at")
        return logs

    @staticmethod
    async def get_login_statistics(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取登录统计信息"""
        query = LoginLog.all()

        if start_time:
            query = query.filter(created_at__gte=start_time)
        if end_time:
            query = query.filter(created_at__lte=end_time)

        total = await query.count()
        success_count = await query.filter(success=True).count()
        failed_count = await query.filter(success=False).count()
        login_count = await query.filter(login_type="login").count()
        logout_count = await query.filter(login_type="logout").count()

        return {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "login": login_count,
            "logout": logout_count,
        }

    @staticmethod
    async def delete_old_logs(days: int = 90) -> int:
        """删除旧日志"""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = await LoginLog.filter(created_at__lt=cutoff_date).delete()
        return deleted_count
