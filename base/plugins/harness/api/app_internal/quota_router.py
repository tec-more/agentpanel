"""app 内部额度 API：供 编排执行预占/结算/释放（服务凭据保护）。

- 额度表归属 app，独立服务不得直连写；本接口是唯一写入口；
- 幂等：reserve 由 quota_reservation.hold_id 唯一约束，settle 由
  usage_record.idem_key 唯一约束（均要求 orch: 前缀），release 天然幂等；
- 失败码：409 状态冲突 / 429 额度不足 / 503 依赖不可用；独立服务侧一律 fail-closed。
- 不在 `api/v1` 下，由 start.py 手动挂载到根路径，避免插件前缀包裹。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from base.common.quota.errors import QuotaError, QuotaReservationConflict
from base.common.quota.services.quota_service import QuotaService
from base.common.response import fail_response, success_response
from base.plugins.harness.services import service_auth
from base.plugins.harness.services.orchestration_config import orchestration_config

app_quota_router = APIRouter(prefix="/internal/v1/harness/quota", tags=["Harness-内部"], include_in_schema=False)

ERROR_NOT_PRIMARY = "orchestration_not_primary"
ERROR_BACKEND = "quota_backend_unavailable"
ERROR_HOLD_ID = "quota_hold_id_required"
ERROR_IDEM = "quota_idempotency_key_required"


class ReserveBody(BaseModel):
    owner_type: str
    owner_id: int
    items: Dict[str, float]
    hold_id: str
    source: str = "client"
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    member_id: Optional[int] = None


class SettleBody(BaseModel):
    hold_id: str = ""
    owner_type: Optional[str] = None
    owner_id: Optional[int] = None
    usage_items: List[Dict[str, Any]] = Field(default_factory=list)


class ReleaseBody(BaseModel):
    hold_id: str
    reason: str = ""


async def _require_service(request: Request):
    try:
        return await service_auth.authenticate(request, ("quota:operate",))
    except service_auth.ServiceAuthError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.status_code, "msg": exc.message, "data": exc.to_dict()},
        )


def _ensure_primary():
    """单写者闸门：app 处于 app 模式（本地编排）时，独立服务不得执行额度写操作。"""
    if str(orchestration_config().get("mode") or "") != "proxy":
        raise HTTPException(
            status_code=409,
            detail={
                "code": 409,
                "msg": "app 当前为本地编排模式，拒绝独立服务额度写操作",
                "data": {"error_code": ERROR_NOT_PRIMARY},
            },
        )


def _fail(status_code: int, error_code: str, msg: str, data: Optional[dict] = None):
    payload = dict(data or {})
    payload["error_code"] = error_code
    return fail_response(data=payload, msg=msg, code=status_code, status_code=status_code)


@app_quota_router.post("/reserve", summary="编排额度预占")
async def reserve(body: ReserveBody, _identity=Depends(_require_service)):
    _ensure_primary()
    if not body.hold_id.startswith("orch:"):
        return _fail(400, ERROR_HOLD_ID, "hold_id 必须为 orch: 前缀（确定性幂等键）")
    try:
        hold_id = await QuotaService.quota_estimate(
            (body.owner_type, int(body.owner_id)),
            body.items,
            hold_id=body.hold_id,
            source=body.source,
            ref_type=body.ref_type,
            ref_id=body.ref_id,
            member_id=body.member_id,
        )
    except QuotaReservationConflict as exc:
        return _fail(409, str(exc.code), str(exc), exc.data)
    except QuotaError as exc:
        data = dict(exc.data)
        data.update({"code": 42901, "error_code": "quota_exceeded", "hold_id": body.hold_id})
        return fail_response(data=data, msg=str(exc), code=42901, status_code=429)
    except Exception as exc:
        logger.exception(f"[quota-api] reserve 失败 hold={body.hold_id}: {exc}")
        return _fail(503, ERROR_BACKEND, f"额度后端不可用: {type(exc).__name__}")
    return success_response(data={"hold_id": hold_id})


@app_quota_router.post("/settle", summary="编排用量结算")
async def settle(body: SettleBody, _identity=Depends(_require_service)):
    _ensure_primary()
    if not body.usage_items:
        return success_response(data={"settled": 0, "skipped": 0})
    for item in body.usage_items:
        key = str(item.get("idem_key") or "")
        if not key.startswith("orch:"):
            return _fail(400, ERROR_IDEM, "每条用量必须带 orch: 前缀的 idem_key")
    owner = None
    if body.owner_type is not None and body.owner_id is not None:
        owner = (body.owner_type, int(body.owner_id))
    try:
        result = await QuotaService.quota_settle(body.hold_id or None, body.usage_items, owner=owner)
    except QuotaReservationConflict as exc:
        return _fail(409, str(exc.code), str(exc), exc.data)
    except QuotaError as exc:
        data = dict(exc.data)
        data.update({"code": 42901, "error_code": "quota_exceeded", "hold_id": body.hold_id})
        return fail_response(data=data, msg=str(exc), code=42901, status_code=429)
    except Exception as exc:
        logger.exception(f"[quota-api] settle 失败 hold={body.hold_id}: {exc}")
        return _fail(503, ERROR_BACKEND, f"额度后端不可用: {type(exc).__name__}")
    return success_response(data=result)


@app_quota_router.post("/release", summary="编排额度释放")
async def release(body: ReleaseBody, _identity=Depends(_require_service)):
    _ensure_primary()
    try:
        released = await QuotaService.quota_release(body.hold_id)
    except Exception as exc:
        logger.exception(f"[quota-api] release 失败 hold={body.hold_id}: {exc}")
        return _fail(503, ERROR_BACKEND, f"额度后端不可用: {type(exc).__name__}")
    return success_response(data={"released": bool(released)})


@app_quota_router.get("/status", summary="编排额度接口状态")
async def status(_identity=Depends(_require_service)):
    cfg = orchestration_config()
    return success_response(data={
        "mode": cfg.get("mode"),
        "write_enabled": bool(cfg.get("write_enabled")),
        "primary": str(cfg.get("mode") or "") == "proxy",
    })
