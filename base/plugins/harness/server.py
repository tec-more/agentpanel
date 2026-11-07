"""L3 编排服务独立进程入口（standalone）

启动方式：
    python -m base.plugins.harness.server
    uvicorn base.plugins.harness.server:app --host 127.0.0.1 --port 9100

职责边界：
- 健康检查与内部认证：/health/* 与 /internal/v1/harness/*；
- P1.2：只读会话/运行/步骤查询 + 心跳（与 L2 同路径）；
- P1.3：9 条额度副作用编排写接口（write_enabled=false 时统一 409），额度写操作
  只经 L2 内部额度 API，不在本进程直连 QuotaService；
- 服务凭据校验，拒绝用户 JWT、网关租约 key、匿名；
- 只读数据库连接做启动自检（写必须被拒）；
- 不执行迁移、不生成表结构（service_credential 由 L2 启动流程创建）。
"""
import io
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from base.common.exceptions import register_exceptions
from base.common.health import router as health_router
from base.plugins.harness.api.internal.router import internal_router
from base.plugins.harness.api.l3.business_router import l3_business_router
from base.plugins.harness.api.l3.write_router import l3_write_router
from base.plugins.harness.services.orchestration_runtime import set_runtime_role
from base.plugins.harness.services.orchestration_config import (
    OrchestrationConfigError,
    orchestration_config,
    validate_orchestration_config,
)
from base.plugins.harness.services.readonly_db import close_readonly_db, get_readonly_db
from base.plugins.harness.services.service_auth import ServiceAuthError


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
    """共享库连接 + 只读连接自检；任一不满足即 fail-closed。"""
    from tortoise import Tortoise

    from base.common.setting import TORTOISE_ORM

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        readonly = get_readonly_db()
        await readonly.connect()

        report = await readonly.verify_readonly()
        if report.get("status") != "healthy":
            raise RuntimeError(f"只读数据库自检未通过，拒绝启动: {report.get('message')}")

        table = await readonly.credential_table_ready()
        if table.get("status") != "healthy":
            raise RuntimeError(f"service_credential 不可用，拒绝启动: {table.get('message')}")

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
        app.state.active_credential_count = active_count
        print(
            f"[orchestration] 启动自检通过：只读库可用且写被拒，service_credential active={active_count}",
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
            "L3 编排服务骨架：只暴露 /health 与 /internal/v1/harness/*；"
            "内部接口仅接受服务凭据（HMAC），不接受用户 JWT、网关租约 key 或匿名。"
        ),
        version="0.1.0",
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

    # 错误响应与 L2 同形（HTTPException/校验/数据库异常）
    register_exceptions(app)

    # /health/health、/health/live、/health/ready（与 L2 同口径，含真实 SELECT 1）
    app.include_router(health_router, prefix="/health")
    app.include_router(internal_router)
    # P1.2 第一批：会话/运行/步骤查询 + 心跳（与 L2 同路径）
    app.include_router(l3_business_router)
    # P1.3：额度副作用编排写接口（write_enabled=false 时统一 409）
    app.include_router(l3_write_router)

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


# 本进程即 L3：额度写操作只能经 L2 内部额度 API（禁止本地直调 QuotaService）
set_runtime_role("l3")
app = build_app()


def main() -> None:
    _configure_stdout()
    cfg = orchestration_config()
    host, port = listen_address()
    print("=" * 70, flush=True)
    print("L3 Harness 编排服务（standalone）启动中...", flush=True)
    print(f"监听地址: http://{host}:{port}", flush=True)
    print(f"deployment: {cfg.get('deployment')}", flush=True)
    print(f"mode: {cfg.get('mode')}  write_enabled: {bool(cfg.get('write_enabled'))}", flush=True)
    print(f"public_base_url: {cfg.get('public_base_url')}", flush=True)
    print("内部接口仅接受服务凭据；用户 JWT / 网关租约 key / 匿名一律拒绝。", flush=True)
    print("=" * 70, flush=True)

    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=True)


if __name__ == "__main__":
    main()
