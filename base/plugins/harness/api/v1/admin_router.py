"""Harness 管理端查询：会话/运行列表与详情（管理员）"""
from typing import Optional

from fastapi import APIRouter, Query

from base.common.permissions import require_superuser
from base.common.quota.models.reservation import QuotaReservation
from base.common.response import success_response, fail_response
from base.plugins.harness.models.harness import HarnessRun, HarnessSession, HarnessStep
from base.plugins.harness.services.dashboard_service import HarnessDashboardService
from base.plugins.harness.services.model_credential_service import (
    HarnessModelCredentialService,
    ModelCredentialNotConfigured,
)
from base.plugins.harness.services.run_service import run_to_dict, session_to_dict, step_to_dict
from base.plugins.harness.services.runtime_service import HarnessRuntimeLauncher

admin_router = APIRouter(prefix="/admin", tags=["Harness-管理"])


def _reservation_dict(row: Optional[QuotaReservation]) -> Optional[dict]:
    if row is None:
        return None
    return {
        "hold_id": row.hold_id,
        "status": row.status,
        "counter_mode": row.counter_mode,
        "items": row.items,
        "used_items": row.used_items,
        "expire_at": row.expire_at.isoformat() if row.expire_at else None,
        "settled_at": row.settled_at.isoformat() if row.settled_at else None,
        "released_at": row.released_at.isoformat() if row.released_at else None,
    }


@admin_router.get("/sessions", summary="会话列表（管理员）")
async def list_sessions(
    client_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    query = HarnessSession.all()
    if client_id:
        query = query.filter(client_id=client_id)
    if user_id:
        query = query.filter(user_id=user_id)
    if status_filter:
        query = query.filter(status=status_filter)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [session_to_dict(s) for s in rows],
    })


@admin_router.get("/sessions/{session_no}", summary="会话详情（含运行与用量）")
async def get_session_detail(session_no: str, admin_id: int = require_superuser()):
    session = await HarnessSession.get_or_none(session_no=session_no)
    if session is None:
        return fail_response(msg="会话不存在", code=404, status_code=404)
    usage = await HarnessDashboardService.session_usage(session_no)
    runs = await HarnessRun.filter(session_no=session_no).order_by("-created_at").limit(50)
    return success_response(data={
        "session": session_to_dict(session),
        "usage": {k: usage[k] for k in ("total", "by_source", "by_kind", "by_model")},
        "runs": [run_to_dict(r) for r in runs],
    })


@admin_router.get("/runs", summary="运行列表（管理员）")
async def list_runs(
    session_no: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    query = HarnessRun.all()
    if session_no:
        query = query.filter(session_no=session_no)
    if client_id:
        query = query.filter(client_id=client_id)
    if status_filter:
        query = query.filter(status=status_filter)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [run_to_dict(r) for r in rows],
    })


@admin_router.get("/runs/{run_no}", summary="运行详情（用量、预占、失败原因）")
async def get_run_detail(run_no: str, admin_id: int = require_superuser()):
    run = await HarnessRun.get_or_none(run_no=run_no)
    if run is None:
        return fail_response(msg="运行不存在", code=404, status_code=404)
    usage = await HarnessDashboardService.run_usage(run_no)
    reservation = await QuotaReservation.get_or_none(hold_id=run.hold_id) if run.hold_id else None
    return success_response(data={
        "run": run_to_dict(run),
        "usage": {k: usage.get(k) for k in ("total", "by_source", "by_kind", "by_model")},
        "reservation": _reservation_dict(reservation),
    })


@admin_router.get("/runs/{run_no}/steps", summary="运行步骤列表（管理员）")
async def list_run_steps(
    run_no: str,
    step_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    admin_id: int = require_superuser(),
):
    run = await HarnessRun.get_or_none(run_no=run_no)
    if run is None:
        return fail_response(msg="运行不存在", code=404, status_code=404)
    query = HarnessStep.filter(run_id=run.id)
    if step_type:
        query = query.filter(step_type=step_type)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("seq")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [step_to_dict(s) for s in rows],
    })


@admin_router.get("/model-credentials", summary="模型凭据列表（脱敏）")
async def list_model_credentials(admin_id: int = require_superuser()):
    rows = await HarnessModelCredentialService.list_configured()
    return success_response(data={"total": len(rows), "items": rows})


@admin_router.get("/model-credentials/effective", summary="生效模型凭据（脱敏）")
async def get_effective_model_credential(
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    admin_id: int = require_superuser(),
):
    try:
        credential = await HarnessModelCredentialService.resolve(provider, model)
    except ModelCredentialNotConfigured as exc:
        return fail_response(msg=exc.message, code=400, status_code=400)
    return success_response(data=credential.redacted())


@admin_router.post("/model-credentials/verify", summary="验证子进程凭据注入（脱敏）")
async def verify_model_credential_injection(
    provider: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    admin_id: int = require_superuser(),
):
    try:
        result = await HarnessRuntimeLauncher.verify_injection(provider=provider, model=model)
    except ModelCredentialNotConfigured as exc:
        return fail_response(msg=exc.message, code=400, status_code=400)
    except RuntimeError as exc:
        return fail_response(msg=str(exc), code=500, status_code=500)
    return success_response(data=result)
