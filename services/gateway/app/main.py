"""L3 网关独立服务入口（services/gateway）。

与旧入口 `base/common/gateway/server.py` 的行为契约一致：
- 端口 9999（本地骨架用 `GW_PORT` 覆盖）、`/health` 形状不变；
- 配置只读环境变量 + 独立 manifest，DB/Redis 必填缺失或非法 → 退出码 2；
- 启动即 fail-closed 配置校验，且独立入口仅允许 `deployment=standalone`。

P3 T3.2/T3.3：数据面逻辑来自同一服务目录下的网关领域包 `services.gateway.common.*`
（跨进程共享：L2 签发租约/看板；编排已解耦，改引共享基础包的网关边界契约）。
P3 T3.5：模型凭据走共享 `domain/credential_resolver`，禁止环境变量兜底。
P3 T3.6：Redis 走共享 `cache.RedisCache`。
P3 D-P3-2=B：套餐解析注入只读 SQL 版，与 L2 ORM 版逐字段对拍。
"""
import io
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from packages.agentpanel_common.cache import RedisCache, configure as configure_cache
from packages.agentpanel_common.config import ConfigError, load_l3_common
from packages.agentpanel_common.db import (
    build_tortoise_orm,
    gateway_dependency_modules,
    shared_model_modules,
    stabilize_shared_model_fields,
)
from packages.agentpanel_common.domain import credential_resolver
from services.gateway.common import runtime as gateway_runtime
from services.gateway.common.router import gateway_data_router
from packages.agentpanel_common.l3_metrics import (
    L3HttpMetricsMiddleware,
    make_metrics_endpoint,
    mark_service,
)
from packages.agentpanel_common.quota.services import plan_service
from packages.agentpanel_common.quota.services.plan_resolver import SqlPlanResolver

from app import health as health_module
from app.config import (
    GatewayConfigError,
    gateway_config,
    gateway_upstream_config,
    lease_cache_ttl_seconds,
    validate_gateway_config,
)

# P3：仍是环境变量契约；必填缺失/类型非法 → 退出码 2（与旧入口一致）
try:
    _L3_CONFIG = load_l3_common(source="gateway")
except ConfigError as exc:
    print(f"❌ [gateway] {exc}", flush=True)
    raise SystemExit(2)


def _configure_shared_runtime() -> None:
    """注入共享网关模块的配置源（不再依赖 base.* / plugin_manager）。"""
    gateway_runtime.configure(
        config_provider=gateway_config,
        upstream_provider=gateway_upstream_config,
        lease_ttl_provider=lambda cfg=None: lease_cache_ttl_seconds(cfg or gateway_config()),
    )
    plan_service.configure(SqlPlanResolver())
    # 网关禁止进程环境变量兜底：凭据只能来自项目自身 LLM 配置
    credential_resolver.configure(
        defaults={"provider": None, "model": None},
        env_fallback=False,
    )


_configure_shared_runtime()


def _configure_stdout() -> None:
    """Windows 控制台默认 GBK；统一 UTF-8，避免中文启动日志乱码。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        buffer = getattr(stream, "buffer", None)
        if buffer is None:
            continue
        try:
            setattr(sys, name, io.TextIOWrapper(buffer, encoding="utf-8"))
        except Exception:
            pass


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """连接共享库与 Redis；退出时释放连接。"""
    from tortoise import Tortoise

    redis_cfg = _L3_CONFIG.redis
    configure_cache(
        enabled=bool(redis_cfg.enabled),
        host=redis_cfg.host,
        port=redis_cfg.port,
        password=redis_cfg.password or None,
        db=redis_cfg.db,
    )
    await RedisCache.get_instance()

    await Tortoise.init(
        config=build_tortoise_orm(
            _L3_CONFIG.db,
            shared_model_modules() + gateway_dependency_modules(),
        )
    )
    stabilize_shared_model_fields()
    health_module.init_health(_L3_CONFIG)
    try:
        yield
    finally:
        cache = await RedisCache.get_instance()
        await cache.close()
        await Tortoise.close_connections()


def _error_type(status_code: int) -> str:
    if status_code in (401, 403):
        return "gateway_auth_error"
    if status_code == 429:
        return "gateway_rate_limit_error"
    if status_code == 400:
        return "invalid_request_error"
    return "gateway_error"


def build_app() -> FastAPI:
    """fail-closed 校验通过后构建数据面应用。"""
    cfg = validate_gateway_config()
    deployment = str(cfg.get("deployment") or "")
    if deployment != "standalone":
        raise GatewayConfigError(
            f"当前 gateway.deployment={deployment}；独立入口仅在 standalone 下启动。"
        )

    app = FastAPI(
        title="AgentPanel 模型透传网关",
        description=(
            "独立数据面服务，仅供桌面端 dsh 使用："
            "只接受 agentpanel 签发的租约虚拟 key（dgw.<lease_id>.<secret>），"
            "不接受任何 JWT / 登录态凭据；SSE 原样透传。"
        ),
        version="1.0.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )

    @app.exception_handler(HTTPException)
    async def _gateway_http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": str(exc.detail), "type": _error_type(int(exc.status_code))}},
        )

    # `/health`、`/chat/completions` 由共享数据面 router 提供
    app.include_router(gateway_data_router)
    app.include_router(health_module.router)

    # T7.4：纯 ASGI 指标中间件（不包装 StreamingResponse，SSE 保持原样透传）；
    # /metrics 抓取时顺带刷新 DB/Redis 健康 Gauge，不依赖 L2 settings 开关。
    app.add_middleware(L3HttpMetricsMiddleware)
    app.add_api_route(
        "/metrics",
        make_metrics_endpoint(
            "l3-gateway",
            {"database": health_module.check_database, "redis": health_module.check_redis},
        ),
        methods=["GET"],
        include_in_schema=False,
    )
    mark_service("l3-gateway", "1.0.0")
    return app


def listen_address() -> Tuple[str, int]:
    cfg = gateway_config()
    host = str(cfg.get("host") or "127.0.0.1")
    port = int(cfg.get("port") or 9999)
    return host, port


try:
    app = build_app()
except GatewayConfigError as exc:
    print(f"❌ [gateway] {exc}", flush=True)
    raise SystemExit(2)


def main() -> None:
    _configure_stdout()
    cfg = gateway_config()
    host, port = listen_address()
    print("=" * 70, flush=True)
    print("L3 模型数据面（standalone）启动中...", flush=True)
    print(f"监听地址: http://{host}:{port}", flush=True)
    print(f"deployment: {cfg.get('deployment')}", flush=True)
    print(f"fail_closed: {bool(cfg.get('fail_closed'))}", flush=True)
    print(f"public_base_url: {cfg.get('public_base_url')}", flush=True)
    print("=" * 70, flush=True)

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=True)


if __name__ == "__main__":
    main()
