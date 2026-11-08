"""网关独立子应用：单独依赖树、单独 OpenAPI 文档（/v1/gateway/docs）。

- 不注册任何业务 API 的全局鉴权依赖；
- 只暴露 /health 与 /chat/completions；
- OpenAPI 单独分组（Gateway-数据面），与主文档 /docs 区分；
- 同一工厂同时服务 standalone（L3 独立进程）与 embedded（挂载到业务 API）。
"""
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .router import gateway_data_router


def _error_type(status_code: int) -> str:
    if status_code in (401, 403):
        return "gateway_auth_error"
    if status_code == 429:
        return "gateway_rate_limit_error"
    if status_code == 400:
        return "invalid_request_error"
    return "gateway_error"


def create_gateway_app(lifespan: Optional[Any] = None) -> FastAPI:
    app = FastAPI(
        title="AgentPanel 模型透传网关",
        description=(
            "独立数据面子应用，仅供桌面端 dsh 使用："
            "只接受 agentpanel 签发的租约虚拟 key（dgw.<lease_id>.<secret>），"
            "不接受任何 JWT / 登录态凭据；SSE 原样透传。"
        ),
        version="1.0.0",
        openapi_tags=[
            {
                "name": "Gateway-数据面",
                "description": "模型透传专用接口（租约虚拟 key 鉴权，与业务 API 隔离）",
            }
        ],
        docs_url="/docs",
        openapi_url="/openapi.json",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.exception_handler(HTTPException)
    async def _gateway_http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": str(exc.detail), "type": _error_type(int(exc.status_code))}},
        )

    # 子应用内部路径为 /health、/chat/completions，挂载后对外即 /v1/gateway/*
    app.include_router(gateway_data_router)
    return app


gateway_app = create_gateway_app()
