"""L3 编排内部 API（仅服务凭据可访问，不对业务/前端暴露）。"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from app.auth import require_service_credential
from app.config import orchestration_config
from app.http import success_response
from app.readonly_db import get_readonly_db

internal_router = APIRouter(
    prefix="/internal/v1/harness",
    tags=["Harness-编排内部"],
    include_in_schema=False,
)


@internal_router.get("/whoami", summary="校验服务凭据并返回身份")
async def whoami(
    request: Request,
    identity: Dict[str, Any] = Depends(require_service_credential()),
):
    cfg = orchestration_config()
    return success_response(
        data={
            **identity,
            "orchestration_mode": cfg.get("mode"),
            "write_enabled": bool(cfg.get("write_enabled")),
        },
        msg="服务凭据有效",
    )


@internal_router.get("/health", summary="编排服务依赖健康检查")
async def internal_health(
    identity: Dict[str, Any] = Depends(require_service_credential("orchestration:read")),
):
    readonly = await get_readonly_db().verify_readonly()
    table = await get_readonly_db().credential_table_ready()
    healthy = readonly.get("status") == "healthy" and table.get("status") == "healthy"
    return success_response(
        data={
            "status": "healthy" if healthy else "unhealthy",
            "checks": {"readonly_database": readonly, "service_credential": table},
        },
        msg="编排依赖健康" if healthy else "编排依赖异常",
        status_code=200 if healthy else 503,
        success=healthy,
    )


@internal_router.post("/write-check", summary="写开关自检（write_enabled=false 时返回 409）")
async def write_check(
    identity: Dict[str, Any] = Depends(require_service_credential("orchestration:write")),
):
    from app.auth import ensure_write_enabled

    ensure_write_enabled()
    return success_response(data={"write_enabled": True}, msg="写接口已启用")
