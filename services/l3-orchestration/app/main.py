"""L3 编排独立服务入口（services/l3-orchestration）。

与 P1 `base/plugins/harness/server.py` 的行为契约一致：
- 端口 9100、`/health/*` 与 `/internal/v1/harness/*` 路径不变；
- 配置只读环境变量，DB/Redis 必填缺失或非法 → 退出码 2；
- 启动自检 fail-closed：只读库写拒绝、service_credential 可读、schema 断言；
- 不 import `base.*`，编排侧 C4（plugin_manager/plugins 包）彻底移除。
"""
import io
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from packages.agentpanel_common.config import ConfigError, load_l3_common
from packages.agentpanel_common.db import (
    build_tortoise_orm,
    shared_model_modules,
    stabilize_shared_model_fields,
)
from packages.agentpanel_common.l3_metrics import (
    L3HttpMetricsMiddleware,
    make_metrics_endpoint,
    mark_service,
)

from app import health as health_module
from app import quota_backend
from app.api.approval import approval_router
from app.api.business import l3_business_router
from app.api.internal import internal_router
from app.api.write import l3_write_router
from app.auth import ServiceAuthError
from app.config import (
    OrchestrationConfigError,
    orchestration_config,
    validate_orchestration_config,
)
from app.http import register_exceptions
from app.readonly_db import close_readonly_db, get_readonly_db, init_readonly_db
from app.schema_check import check_schema

# P2：仍是环境变量契约；必填缺失/类型非法 → 退出码 2（与 P1 一致）
try:
    _L3_CONFIG = load_l3_common(source="orchestration")
except ConfigError as exc:
    print(f"❌ [orchestration] {exc}", flush=True)
    raise SystemExit(2)


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
    """共享库连接 + 只读连接/schema 自检；任一不满足即 fail-closed。"""
    from tortoise import Tortoise

    init_readonly_db(_L3_CONFIG.db)
    health_module.init_health(_L3_CONFIG)
    quota_backend.configure_l3()

    await Tortoise.init(
        config=build_tortoise_orm(_L3_CONFIG.db, shared_model_modules())
    )
    stabilize_shared_model_fields()
    try:
        readonly = get_readonly_db()
        await readonly.connect()

        report = await readonly.verify_readonly()
        if report.get("status") != "healthy":
            raise RuntimeError(f"只读数据库自检未通过，拒绝启动: {report.get('message')}")

        table = await readonly.credential_table_ready()
        if table.get("status") != "healthy":
            raise RuntimeError(f"service_credential 不可用，拒绝启动: {table.get('message')}")

        cfg = orchestration_config()
        schema = await check_schema(readonly, cfg.get("schema_min_version"))

        rows = await readonly.fetch(
            "SELECT COUNT(*) AS c FROM service_credential WHERE status = 'active'"
        )
        active_count = int(rows[0]["c"]) if rows else 0
        if active_count == 0:
            print(
                "[orchestration] 警告：service_credential 无 active 凭据，所有内部请求将返回 401",
                flush=True,
            )

        app.state.readonly_report = report
        app.state.credential_table = table
        app.state.schema_report = schema
        app.state.active_credential_count = active_count
        print(
            "[orchestration] 启动自检通过："
            f"只读库可用且写被拒，schema=v{schema.get('schema_version')}，"
            f"service_credential active={active_count}",
            flush=True,
        )
        yield
    finally:
        await close_readonly_db()
        await Tortoise.close_connections()


def build_app() -> FastAPI:
    """fail-closed 校验通过后构建编排应用。"""
    cfg = validate_orchestration_config()

    app = FastAPI(
        title="AgentPanel Harness 编排服务",
        description=(
            "L3 编排独立服务：/health 与 /internal/v1/harness/*；"
            "内部接口仅接受服务凭据（HMAC），不接受用户 JWT、网关租约 key 或匿名。"
        ),
        version="0.2.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        redoc_url=None,
        lifespan=_lifespan,
    )

    @app.exception_handler(ServiceAuthError)
    async def _service_auth_error_handler(request, exc: ServiceAuthError):
        # 与 L2 HttpExcHandle 同形：{code, msg, data}，错误码放在 data.error_code
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "msg": exc.message, "data": exc.to_dict()},
        )

    @app.exception_handler(OrchestrationConfigError)
    async def _config_error_handler(request, exc: OrchestrationConfigError):
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "msg": str(exc),
                "data": {"error_code": "orchestration_config_invalid", "message": str(exc)},
            },
        )

    register_exceptions(app)

    # /health/health、/health/live、/health/ready（与 L2 同口径，含真实 SELECT 1）
    app.include_router(health_module.router, prefix="/health")
    app.include_router(internal_router)
    app.include_router(l3_business_router)
    app.include_router(l3_write_router)
    app.include_router(approval_router, prefix="/v1/harness")

    # T7.4：与网关同口径的 HTTP 指标 + 健康 Gauge；/metrics 不纳入业务鉴权。
    app.add_middleware(L3HttpMetricsMiddleware)
    app.add_api_route(
        "/metrics",
        make_metrics_endpoint(
            "l3-orchestration",
            {"database": health_module.check_database, "redis": health_module.check_redis},
        ),
        methods=["GET"],
        include_in_schema=False,
    )
    mark_service("l3-orchestration", "0.2.0")

    @app.get("/health/orchestration", include_in_schema=True, tags=["编排-健康"])
    async def orchestration_health():
        """编排专属健康：只读库写拒绝探针 + 凭据表可读性。"""
        readonly = await get_readonly_db().verify_readonly()
        table = await get_readonly_db().credential_table_ready()
        healthy = readonly.get("status") == "healthy" and table.get("status") == "healthy"
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "healthy" if healthy else "unhealthy",
                "mode": cfg.get("mode"),
                "write_enabled": bool(cfg.get("write_enabled")),
                "checks": {"readonly_database": readonly, "service_credential": table},
            },
        )

    return app


def listen_address() -> Tuple[str, int]:
    cfg = orchestration_config()
    host = str(cfg.get("host") or "127.0.0.1")
    port = int(cfg.get("port") or 9100)
    return host, port


app = build_app()


def main() -> None:
    _configure_stdout()
    cfg = orchestration_config()
    host, port = listen_address()
    print("=" * 70, flush=True)
    print("L3 Harness 编排服务（standalone，独立工程）启动中...", flush=True)
    print(f"监听地址: http://{host}:{port}", flush=True)
    print(f"deployment: {cfg.get('deployment')}", flush=True)
    print(f"mode: {cfg.get('mode')}  write_enabled: {bool(cfg.get('write_enabled'))}", flush=True)
    print(f"public_base_url: {cfg.get('public_base_url')}", flush=True)
    print(f"L2 内部额度 API: {cfg.get('l2_internal_base_url')}", flush=True)
    print("内部接口仅接受服务凭据；用户 JWT / 网关租约 key / 匿名一律拒绝。", flush=True)
    print("=" * 70, flush=True)

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=True)


if __name__ == "__main__":
    main()
