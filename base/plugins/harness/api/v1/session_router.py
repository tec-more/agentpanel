"""Harness 会话生命周期（客户端凭据鉴权）"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from base.common.response import success_response
from base.plugins.harness.models.harness import HarnessRun, HarnessSession
from base.plugins.harness.schemas.harness import RunCreate, SessionCreate
from base.plugins.harness.services.orchestration_proxy import (
    proxy_mode_enabled,
    proxy_to_orchestration,
    require_client_or_proxy,
)
from base.plugins.harness.services.run_service import HarnessRunService, run_to_dict, session_to_dict

session_router = APIRouter(prefix="/sessions", tags=["Harness-会话"])


@session_router.post("", summary="创建 Harness 会话")
async def create_session(
    payload: SessionCreate,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    session = await HarnessRunService.create_session(payload, client.client_id)
    return success_response(data=session_to_dict(session), msg="会话已创建")


@session_router.get("/{session_no}", summary="查询会话")
async def get_session(session_no: str, request: Request, client=Depends(require_client_or_proxy)):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    session = await HarnessSession.get_or_none(session_no=session_no)
    if session is None or session.client_id != client.client_id:
        return success_response(data=None, msg="会话不存在")
    return success_response(data=session_to_dict(session))


@session_router.post("/{session_no}/close", summary="关闭会话")
async def close_session(
    session_no: str,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    session = await HarnessRunService.close_session(session_no, client.client_id)
    return success_response(data=session_to_dict(session), msg="会话已关闭")


@session_router.post("/{session_no}/runs", summary="创建运行（含配额预占）")
async def create_run(
    session_no: str,
    payload: RunCreate,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    run = await HarnessRunService.create_run(session_no, client.client_id, payload)
    return success_response(data=run_to_dict(run), msg="运行已创建")


@session_router.get("/{session_no}/runs", summary="会话下的运行列表")
async def list_session_runs(
    session_no: str,
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    query = HarnessRun.filter(session_no=session_no, client_id=client.client_id)
    if status_filter:
        query = query.filter(status=status_filter)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [run_to_dict(r) for r in rows],
    })
