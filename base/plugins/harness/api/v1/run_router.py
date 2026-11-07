"""Harness 运行生命周期与事件回传（客户端凭据鉴权）"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from base.common.response import success_response
from base.plugins.harness.models.harness import HarnessRun, HarnessStep
from base.plugins.harness.schemas.harness import EventBatch, RunComplete, StepEvent
from base.plugins.harness.services.orchestration_proxy import (
    proxy_mode_enabled,
    proxy_to_orchestration,
    require_client_or_proxy,
)
from base.plugins.harness.services.event_service import HarnessEventService
from base.plugins.harness.services.run_service import (
    HarnessRunService,
    run_to_dict,
    step_to_dict,
)

run_router = APIRouter(prefix="/runs", tags=["Harness-运行"])


@run_router.get("/{run_no}", summary="查询运行")
async def get_run(run_no: str, request: Request, client=Depends(require_client_or_proxy)):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    run = await HarnessRun.get_or_none(run_no=run_no)
    if run is None or run.client_id != client.client_id:
        return success_response(data=None, msg="运行不存在")
    return success_response(data=run_to_dict(run))


@run_router.post("/{run_no}/start", summary="开始运行")
async def start_run(
    run_no: str,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    run = await HarnessRunService.start_run(run_no, client.client_id)
    return success_response(data=run_to_dict(run), msg="运行已开始")


@run_router.post("/{run_no}/heartbeat", summary="运行心跳")
async def heartbeat(run_no: str, request: Request, client=Depends(require_client_or_proxy)):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    run = await HarnessRunService.heartbeat(run_no, client.client_id)
    return success_response(data=run_to_dict(run))


@run_router.post("/{run_no}/steps", summary="上报步骤事件（含 usage 明细）")
async def ingest_step(
    run_no: str,
    payload: StepEvent,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    step = await HarnessRunService.ingest_step(run_no, client.client_id, payload)
    return success_response(data=step_to_dict(step), msg="步骤已记录")


@run_router.post("/{run_no}/events", summary="采集 JSONL/通知事件（容忍截断与未知类型）")
async def ingest_events(
    run_no: str,
    payload: EventBatch,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    counters = await HarnessEventService.ingest(run_no, client.client_id, payload)
    return success_response(data=counters, msg="事件已采集")


@run_router.get("/{run_no}/steps", summary="运行步骤列表")
async def list_steps(
    run_no: str,
    request: Request,
    step_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    run = await HarnessRun.get_or_none(run_no=run_no)
    if run is None or run.client_id != client.client_id:
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


@run_router.post("/{run_no}/complete", summary="结束运行并结算用量")
async def complete_run(
    run_no: str,
    payload: RunComplete,
    request: Request,
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    run = await HarnessRunService.complete_run(run_no, client.client_id, payload)
    return success_response(data=run_to_dict(run), msg="运行已结束")


@run_router.post("/{run_no}/cancel", summary="取消运行并释放预占")
async def cancel_run(
    run_no: str,
    request: Request,
    reason: Optional[str] = Query(None, description="取消原因"),
    client=Depends(require_client_or_proxy),
):
    if proxy_mode_enabled():
        return await proxy_to_orchestration(request)
    run = await HarnessRunService.cancel_run(run_no, client.client_id, reason)
    return success_response(data=run_to_dict(run), msg="运行已取消")
