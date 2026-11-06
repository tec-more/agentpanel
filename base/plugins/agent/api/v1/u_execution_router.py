"""
用户侧执行 API（dry-run SSE / 取消 / HITL 恢复 / 历史 / Trace）

溯源：
- docs/arch/04 §2.1：POST /u/workflows/{id}/dry-run（SSE）、POST /u/executions/{id}/cancel、
  POST /u/executions/{id}/resume、GET /u/executions、GET /u/executions/{id}、
  GET /u/executions/{id}/trace
- docs/arch/04 F2：试跑以 draft JSON 执行（kind=dry_run，不写长期记忆，单用户并发=1）
- docs/arch/05 §1.2：HITL 恢复状态机校验（仅 paused → running，重复提交返回当前状态）
- docs/arch/06 R-01/R-02：归属过滤在接入层完成（404 不暴露存在性），引擎只消费上下文

路由前缀：/u（在 agent 插件 /v1/agent 下注册，位于 workflow 参数路由之前）。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from base.common.authz import OwnerContext, OwnedResourceNotFound, get_owned_or_404, require_owner
from base.common.quota.errors import QuotaError
from base.common.response import success_response
from base.plugins.agent.models.workflow import Workflow
from base.plugins.agent.services.execution_service import ExecutionService
from base.plugins.agent.services.graph_validator import (
    DOMAIN_USER,
    has_blocking_errors,
)
from base.plugins.agent.services.trace_service import TraceService
from base.plugins.agent.services.workflow_service import WorkflowService

router = APIRouter(prefix="/u", tags=["用户侧执行"])


class DryRunRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict, description="试跑输入变量")


class ResumeRequest(BaseModel):
    approved: bool = Field(..., description="审批结果")
    comment: str = Field("", max_length=500, description="审批意见")


def _execution_payload(e) -> Dict[str, Any]:
    return {
        "id": e.id,
        "workflow_id": e.workflow_id,
        "version_id": e.version_id,
        "kind": e.kind,
        "status": e.status,
        "input_data": e.input_data,
        "output_data": e.output_data,
        "error_message": e.error_message,
        "started_at": e.started_at,
        "completed_at": e.completed_at,
        "created_at": e.created_at,
    }


def _raise_quota(exc: QuotaError):
    raise HTTPException(status_code=429, detail={
        "code": exc.code,
        "msg": exc.message,
        "data": exc.data,
    })


# ============================================================
# 试跑（F2：草稿态，SSE）
# ============================================================
@router.post("/workflows/{workflow_id}/dry-run", summary="试跑工作流（SSE）")
async def dry_run_workflow(
    workflow_id: int,
    body: DryRunRequest,
    owner: OwnerContext = Depends(require_owner),
):
    try:
        wf = await get_owned_or_404(Workflow, workflow_id, owner)
    except OwnedResourceNotFound:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    graph = wf.definition or {}
    # R-03：运行前服务端全量校验（不信任前端/历史校验结果）
    issues = await WorkflowService.validate_graph_for(owner, graph, domain=DOMAIN_USER)
    if has_blocking_errors(issues):
        raise HTTPException(status_code=422, detail={
            "code": 42200, "msg": "校验未通过，无法试跑", "issues": issues,
        })
    try:
        ctx = await ExecutionService.prepare(
            owner, workflow=wf, graph=graph, inputs=body.inputs, kind="dry_run",
        )
    except QuotaError as e:
        _raise_quota(e)

    async def stream():
        try:
            async for frame in ExecutionService.stream_events(ctx, graph, body.inputs):
                yield frame
        except Exception as exc:  # SSE 通道异常兜底（引擎内部异常已转为事件）
            import json as _json

            yield f"event: run_failed\ndata: {_json.dumps({'execution_id': ctx.execution_id, 'error': {'code': 'STREAM_ERROR', 'message': str(exc)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Execution-Id": str(ctx.execution_id),
        },
    )


# ============================================================
# 取消 / HITL 恢复
# ============================================================
@router.post("/executions/{execution_id}/cancel", response_model=dict, summary="取消执行")
async def cancel_execution(
    execution_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    execution = await ExecutionService.get_execution(owner, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    status = await ExecutionService.cancel(execution_id)
    return success_response(data={"id": execution_id, "status": status}, msg="已请求取消")


@router.post("/executions/{execution_id}/resume", response_model=dict, summary="HITL 恢复执行")
async def resume_execution(
    execution_id: int,
    body: ResumeRequest,
    owner: OwnerContext = Depends(require_owner),
):
    # cus P0 仅 self 审批（F6/N4-5）：归属过滤保证 caller 即执行属主
    execution = await ExecutionService.get_execution(owner, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    accepted, status = await ExecutionService.resume(
        execution_id, approved=body.approved, comment=body.comment
    )
    if not accepted:
        # 幂等：非 paused 重复提交返回当前状态（05-§1.2）
        return success_response(
            data={"id": execution_id, "status": status, "accepted": False},
            msg="当前状态不可恢复",
        )
    return success_response(
        data={"id": execution_id, "status": status, "accepted": True},
        msg="已恢复执行",
    )


# ============================================================
# 历史 / 详情 / Trace
# ============================================================
@router.get("/executions", response_model=dict, summary="运行历史")
async def list_executions(
    workflow_id: Optional[int] = None,
    kind: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    owner: OwnerContext = Depends(require_owner),
):
    executions = await ExecutionService.list_executions(
        owner, workflow_id=workflow_id, kind=kind, skip=skip, limit=limit
    )
    return success_response(data=[_execution_payload(e) for e in executions])


@router.get("/executions/{execution_id}", response_model=dict, summary="执行详情")
async def get_execution(
    execution_id: int,
    owner: OwnerContext = Depends(require_owner),
):
    execution = await ExecutionService.get_execution(owner, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    return success_response(data=_execution_payload(execution))


@router.get("/executions/{execution_id}/trace", response_model=dict, summary="Trace 事件分页")
async def get_execution_trace(
    execution_id: int,
    cursor: int = Query(0, ge=0, description="断线补齐起点（last_seq）"),
    limit: int = Query(200, ge=1, le=1000),
    owner: OwnerContext = Depends(require_owner),
):
    execution = await ExecutionService.get_execution(owner, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="资源不存在或无权访问")
    events = await TraceService.list_events(execution_id, cursor=cursor, limit=limit)
    return success_response(data={
        "execution_id": execution_id,
        "cursor": cursor,
        "next_cursor": events[-1].seq if events else cursor,
        "events": [
            {
                "seq": ev.seq,
                "event_type": ev.event_type,
                "node_id": ev.node_id,
                "payload": ev.payload,
                "created_at": ev.created_at,
            }
            for ev in events
        ],
    })
