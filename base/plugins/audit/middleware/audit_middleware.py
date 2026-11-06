import json
import time
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from base.common.setting import settings
from base.plugins.audit.models.audit_log import AuditLog, AuditConfig


class AuditMiddleware(BaseHTTPMiddleware):
    """审计中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.exclude_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/static",
            "/favicon.ico",
        ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        
        path = request.url.path
        
        if any(path.startswith(exclude) for exclude in self.exclude_paths):
            return await call_next(request)
        
        if not getattr(settings, 'AUDIT_ENABLED', True) or not getattr(settings, 'AUDIT_LOG_HTTP_REQUESTS', True):
            return await call_next(request)
        
        module_name = self._extract_module_name(path)
        
        user_id = None
        username = None
        
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id
        if hasattr(request.state, "username"):
            username = request.state.username
        
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    request_body = json.loads(body.decode("utf-8"))
                    request._body = body
            except Exception:
                pass
        
        request_params = dict(request.query_params)
        
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent")
        
        response = await call_next(request)
        
        duration = int((time.time() - start_time) * 1000)
        
        level = "info"
        if response.status_code >= 500:
            level = "critical"
        elif response.status_code >= 400:
            level = "error"
        
        error_message = None
        if response.status_code >= 400:
            error_message = f"HTTP {response.status_code}"
        
        try:
            await AuditLog.create(
                trace_id=None,
                user_id=user_id,
                username=username,
                module=module_name,
                operation=self._extract_operation(request.method, path),
                method=request.method,
                path=path,
                ip_address=ip_address,
                user_agent=user_agent,
                request_params=request_params if request_params else request_body,
                response_data=None,
                status_code=response.status_code,
                error_message=error_message,
                duration=duration,
                level=level,
                business_no=None,
                related_record_id=None,
                status="pending",
            )
        except Exception as e:
            print(f"Failed to create audit log: {e}")
        
        return response

    def _extract_module_name(self, path: str) -> str:
        """从路径中提取模块名"""
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[1]
        return "default"

    def _extract_operation(self, method: str, path: str) -> str:
        """提取操作描述"""
        return f"{method} {path}"

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """获取客户端IP"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else None

    def _mask_sensitive_fields(self, data: dict, sensitive_fields: list) -> dict:
        """脱敏敏感字段"""
        if not data or not sensitive_fields:
            return data
        
        masked_data = data.copy()
        for key, value in masked_data.items():
            if key.lower() in [field.lower() for field in sensitive_fields]:
                masked_data[key] = "***"
            elif isinstance(value, dict):
                masked_data[key] = self._mask_sensitive_fields(value, sensitive_fields)
            elif isinstance(value, list):
                masked_data[key] = [
                    self._mask_sensitive_fields(item, sensitive_fields) if isinstance(item, dict) else item
                    for item in value
                ]
        return masked_data


ENABLED = True
