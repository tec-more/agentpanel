"""
L1 接入层中间件：owner 上下文注入 + 越权限流闸门

溯源：
- docs/arch/05 §2.1 L1：JWT typ/sub 同源校验（复用 base.common.security），统一注入 owner 上下文
- docs/arch/04 §F8：高频越权（同主体 1 分钟 >10 次）→ 限流
- R-04：信任 typ/sub 同源，禁止兼容旧 token 语义

挂载机制：经 base.common.middleware 自动发现（base_packages 含 "base.common"）。
PRIORITY=5：低于审计 TraceMiddleware(10)，保证 trace_id 已注入后再执行本中间件。

行为说明：
- 本中间件不做全局强制鉴权（登录等公开端点存在）；
  需要认证的端点由 require_owner 依赖 / L2 过滤器各自把关（401）。
- 持有合法 token 的请求：解析注入完整 OwnerContext（usr 已叠加 RBAC data_scope）。
- 处于越权限流封禁期的主体：直接 429（F8）。
"""
from dataclasses import replace

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from base.common.authz.audit import is_rate_limited, record_rate_limited_hit
from base.common.authz.context import (
    clear_owner_context,
    parse_owner_token,
    resolve_full_owner,
    set_owner_context,
)
from base.common.setting import settings

ENABLED = True
# 数值越小越早注册（越晚执行）；确保在 TraceMiddleware(10) 之后运行以继承 trace_id
PRIORITY = 5


class AuthzContextMiddleware(BaseHTTPMiddleware):
    """JWT 双主体上下文注入 + F8 越权限流闸门"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.exclude_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/static",
            "/favicon.ico",
            "/metrics",
        ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if any(path.startswith(exclude) for exclude in self.exclude_paths):
            return await call_next(request)

        owner = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            base_owner = parse_owner_token(auth_header[7:])
            if base_owner is not None:
                base_owner = replace(
                    base_owner,
                    request_path=path,
                    request_method=request.method,
                )
                try:
                    # usr 叠加现有 RBAC data_scope（DB 查询；安装向导等无 DB 场景降级为 self）
                    owner = await resolve_full_owner(base_owner)
                except Exception:
                    owner = base_owner

        # F8 限流闸门：封禁期主体直接 429
        if owner is not None and await is_rate_limited(owner.identity):
            await record_rate_limited_hit(
                owner.identity, path=path, method=request.method
            )
            return JSONResponse(
                status_code=429,
                content={"code": 42901, "msg": "请求过于频繁，请稍后再试", "data": None},
            )

        # 注入请求上下文（L2 过滤 / L3 复核 / 审计均从此读取）
        set_owner_context(owner)
        request.state.owner = owner
        try:
            return await call_next(request)
        finally:
            clear_owner_context()


def is_authz_middleware_enabled() -> bool:
    return ENABLED and getattr(settings, "AUTHZ_CONTEXT_ENABLED", True)
