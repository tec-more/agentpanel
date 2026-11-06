import json
import time
from datetime import datetime
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from base.common.context import (
    set_trace_id,
    clear_trace_id,
    set_user_context,
    clear_user_context,
    get_current_trace_id,
    current_user_id,
    current_username
)
from base.plugins.audit.services.audit_service import (
    generate_trace_id,
    AuditLogService,
    InputLayerService,
    OutputLayerService
)
from base.plugins.audit.schemas.audit_log import (
    InputLayerLogCreate,
    OutputLayerLogCreate,
    AuditLogCreate
)
from base.common.setting import settings


ENABLED = getattr(settings, 'TRACE_ENABLED', True)
PRIORITY = 10


def is_trace_enabled() -> bool:
    return ENABLED


class TraceMiddleware(BaseHTTPMiddleware):
    """全链路追踪中间件 - 自动埋点"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.exclude_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/static",
            "/favicon.ico",
            "/v1/auth/login",
            "/v1/auth/logout",
        ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not is_trace_enabled():
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(exclude) for exclude in self.exclude_paths):
            return await call_next(request)

        start_time = time.time()
        trace_id = request.headers.get("X-Trace-ID", generate_trace_id())
        set_trace_id(trace_id)
        request.state.trace_id = trace_id

        user_id = None
        username = None

        try:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                from base.common.security import decode_access_token
                token_data = decode_access_token(auth_header[7:])
                if token_data:
                    uid = token_data.get("sub")
                    uname = token_data.get("username")
                    if uid:
                        user_id = int(uid)
                        username = uname
                        set_user_context(user_id, uname)
                        request.state.user_id = user_id
                        request.state.username = username

            request_body = None
            try:
                body = await request.body()
                if body:
                    request_body = json.loads(body.decode("utf-8"))
            except:
                pass

            input_data = {}
            if request_body:
                input_data = request_body
            input_data.update(dict(request.query_params))

            await InputLayerService.create_log(InputLayerLogCreate(
                trace_id=trace_id,
                user_id=user_id,
                username=username,
                user_instruction=f"{request.method} {request.url.path}",
                context_data=input_data if input_data else None
            ))

            response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id

            duration = int((time.time() - start_time) * 1000)

            output_data = ""
            try:
                if hasattr(response, 'body') and response.body:
                    output_data = response.body.decode('utf-8')[:1000]
            except:
                pass

            await OutputLayerService.create_log(OutputLayerLogCreate(
                trace_id=trace_id,
                final_output=output_data,
                format_compliance=True
            ))

            level = "info"
            if response.status_code >= 500:
                level = "error"
            elif response.status_code >= 400:
                level = "warning"

            module = self._get_module_from_path(request.url.path)

            await AuditLogService.create_log(AuditLogCreate(
                trace_id=trace_id,
                user_id=user_id,
                username=username,
                module=module,
                operation=f"{request.method} {request.url.path}",
                method=request.method,
                path=str(request.url.path),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                status_code=response.status_code,
                duration=duration,
                level=level,
                business_no=trace_id
            ))

            return response

        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            
            await AuditLogService.create_log(AuditLogCreate(
                trace_id=trace_id,
                user_id=user_id,
                username=username,
                module=self._get_module_from_path(request.url.path),
                operation=f"{request.method} {request.url.path}",
                method=request.method,
                path=str(request.url.path),
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                status_code=500,
                error_message=str(e),
                duration=duration,
                level="error",
                business_no=trace_id
            ))
            
            raise

        finally:
            clear_trace_id()
            clear_user_context()

    def _get_module_from_path(self, path: str) -> str:
        """从路径中提取模块名称"""
        parts = path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[1]
        return "unknown"
