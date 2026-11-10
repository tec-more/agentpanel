"""编排业务路由（P1.2 第一批：无额度副作用的查询 + 心跳）

- 路径与 app `/v1/harness` 完全一致，客户端可直连 9100；
- 只读：session/run/step 查询不产生任何写操作；
- 心跳只定向更新 `last_heartbeat_at`，不整行 save，避免与 app 仍在写状态字段时互相覆盖；
- 客户端凭据只读校验，`last_used_at` 经 app 内部接口异步上报。
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.http import success_response
from packages.common.models.harness import HarnessRun, HarnessSession, HarnessStep
from app import auth as service_auth
from app.client_auth import require_harness_client_readonly
from packages.common.domain.run_service import (
    TERMINAL_STATUSES,
    run_to_dict,
    session_to_dict,
    step_to_dict,
)

business_router = APIRouter(prefix="/v1/harness", tags=["Harness-编排业务"])


@business_router.get("/sessions/{session_no}", summary="查询会话")
async def get_session(
    session_no: str,
    client=Depends(require_harness_client_readonly),
):
    session = await HarnessSession.get_or_none(session_no=session_no)
    if session is None or session.client_id != client["client_id"]:
        return success_response(data=None, msg="会话不存在")
    return success_response(data=session_to_dict(session))


@business_router.get("/sessions/{session_no}/runs", summary="会话下的运行列表")
async def list_session_runs(
    session_no: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    client=Depends(require_harness_client_readonly),
):
    query = HarnessRun.filter(session_no=session_no, client_id=client["client_id"])
    if status_filter:
        query = query.filter(status=status_filter)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [run_to_dict(r) for r in rows],
    })


@business_router.get("/runs/{run_no}", summary="查询运行")
async def get_run(run_no: str, client=Depends(require_harness_client_readonly)):
    run = await HarnessRun.get_or_none(run_no=run_no)
    if run is None or run.client_id != client["client_id"]:
        return success_response(data=None, msg="运行不存在")
    return success_response(data=run_to_dict(run))


@business_router.get("/runs/{run_no}/steps", summary="运行步骤列表")
async def list_steps(
    run_no: str,
    step_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    client=Depends(require_harness_client_readonly),
):
    run = await HarnessRun.get_or_none(run_no=run_no)
    if run is None or run.client_id != client["client_id"]:
        return success_response(data=None, msg="运行不存在")
    query = HarnessStep.filter(run_id=run.id)
    if step_type:
        query = query.filter(step_type=step_type)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("seq")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [step_to_dict(r) for r in rows],
    })


@business_router.post("/runs/{run_no}/heartbeat", summary="运行心跳")
async def heartbeat(run_no: str, client=Depends(require_harness_client_readonly)):
    service_auth.ensure_write_enabled()

    run = await HarnessRun.get_or_none(run_no=run_no)
    if run is None or run.client_id != client["client_id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行不存在")
    if run.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="运行已结束")

    now = datetime.now()
    # 定向更新：与 app `run.save()` 的可观察结果一致，但不整行覆盖，
    # 避免与仍可能由 app 写入的 status 等字段互相踩写。
    # updated_at 与 Tortoise auto_now 同口径（UTC aware），保证与 app 写入值一致。
    await HarnessRun.filter(id=run.id).update(
        last_heartbeat_at=now, updated_at=datetime.now(timezone.utc)
    )
    run.last_heartbeat_at = now
    return success_response(data=run_to_dict(run))
