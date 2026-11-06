from base.common.events.base_handler import BaseEventHandler
from base.plugins.audit.services.login_log_service import LoginLogService
from base.common.setting import settings
from loguru import logger


class LoginEventHandler(BaseEventHandler):
    """登录事件处理器"""

    enabled = True
    priority = 50

    def is_enabled(self) -> bool:
        return self.enabled and getattr(settings, 'AUDIT_ENABLED', True) and getattr(settings, 'AUDIT_LOG_LOGIN', True)

    async def handle(self, event_name: str, **kwargs):
        if not self.is_enabled():
            return

        user_id = kwargs.get('user_id')
        username = kwargs.get('username')
        login_type = kwargs.get('login_type')
        login_method = kwargs.get('login_method')
        ip_address = kwargs.get('ip_address')
        user_agent = kwargs.get('user_agent')
        success = kwargs.get('success', True)
        fail_reason = kwargs.get('fail_reason')

        try:
            await LoginLogService.create_log({
                "user_id": user_id,
                "username": username,
                "login_type": login_type,
                "login_method": login_method,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "success": success,
                "fail_reason": fail_reason,
            })
            logger.debug(f"记录登录日志: {username} {login_type} {success}")
        except Exception as e:
            logger.error(f"记录登录日志失败: {e}")