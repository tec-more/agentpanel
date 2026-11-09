"""L3 编排写接口（P1.3）：与 L2 同路径、同请求/响应契约。

顺序固定：客户端凭据校验 → write_enabled 总开关（false 时 409）→ 复用
HarnessRunService / HarnessEventService / HarnessPolicyService，保证状态机与
错误码与 L2 本地实现同源。额度写操作由 quota_backend 转发到 L2 内部 API。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.http import success_response
from packages.common.domain.schemas import (
    ActionEvaluate,
    EventBatch,
    RunComplete,
    RunCreate,
    SessionCreate,
    StepEvent,
)
from app import auth as service_auth
from packages.common.domain.audit_service import HarnessAuditService
from packages.common.domain.event_service import HarnessEventService
from app.l3_client_auth import require_harness_client_readonly
from packages.common.domain.policy_service import HarnessPolicyService
from packages.common.domain.run_service import (
    HarnessRunService,
    run_to_dict,
    session_to_dict,
    step_to_dict,
)

l3_write_router = APIRouter(prefix="/v1/harness", tags=["Harness-编排写"])


def _client_id(client) -> str:
    return str(client["client_id"] if isinstance(client, dict) else client.client_id)


@l3_write_router.post("/sessions", summary="创建 Harness 会话")
async def create_session(payload: SessionCreate, client=Depends(require_harness_client_readonly)):
    service_auth.ensure_write_enabled()
    session = await HarnessRunService.create_session(payload, _client_id(client))
    return success_response(data=session_to_dict(session), msg="会话已创建")


@l3_write_router.post("/sessions/{session_no}/close", summary="关闭会话")
async def close_session(session_no: str, client=Depends(require_harness_client_readonly)):
    service_auth.ensure_write_enabled()
    session = await HarnessRunService.close_session(session_no, _client_id(client))
    return success_response(data=session_to_dict(session), msg="会话已关闭")


@l3_write_router.post("/sessions/{session_no}/runs", summary="创建运行（含配额预占）")
async def create_run(
    session_no: str,
    payload: RunCreate,
    client=Depends(require_harness_client_readonly),
):
    service_auth.ensure_write_enabled()
    run = await HarnessRunService.create_run(session_no, _client_id(client), payload)
    return success_response(data=run_to_dict(run), msg="运行已创建")


@l3_write_router.post("/runs/{run_no}/start", summary="开始运行")
async def start_run(run_no: str, client=Depends(require_harness_client_readonly)):
    service_auth.ensure_write_enabled()
    run = await HarnessRunService.start_run(run_no, _client_id(client))
    return success_response(data=run_to_dict(run), msg="运行已开始")


@l3_write_router.post("/runs/{run_no}/steps", summary="上报步骤事件（含 usage 明细）")
async def ingest_step(
    run_no: str,
    payload: StepEvent,
    client=Depends(require_harness_client_readonly),
):
    service_auth.ensure_write_enabled()
    step = await HarnessRunService.ingest_step(run_no, _client_id(client), payload)
    return success_response(data=step_to_dict(step), msg="步骤已记录")


@l3_write_router.post("/runs/{run_no}/events", summary="采集 JSONL/通知事件")
async def ingest_events(
    run_no: str,
    payload: EventBatch,
    client=Depends(require_harness_client_readonly),
):
    service_auth.ensure_write_enabled()
    counters = await HarnessEventService.ingest(run_no, _client_id(client), payload)
    return success_response(data=counters, msg="事件已采集")


@l3_write_router.post("/runs/{run_no}/complete", summary="结束运行并结算用量")
async def complete_run(
    run_no: str,
    payload: RunComplete,
    client=Depends(require_harness_client_readonly),
):
    service_auth.ensure_write_enabled()
    run = await HarnessRunService.complete_run(run_no, _client_id(client), payload)
    return success_response(data=run_to_dict(run), msg="运行已结束")


@l3_write_router.post("/runs/{run_no}/cancel", summary="取消运行并释放预占")
async def cancel_run(
    run_no: str,
    reason: Optional[str] = Query(None, description="取消原因"),
    client=Depends(require_harness_client_readonly),
):
    service_auth.ensure_write_enabled()
    run = await HarnessRunService.cancel_run(run_no, _client_id(client), reason)
    return success_response(data=run_to_dict(run), msg="运行已取消")


@l3_write_router.post("/policies/evaluate", summary="动作安全评估（三档判定，未命中转人工）")
async def evaluate_action(
    payload: ActionEvaluate,
    client=Depends(require_harness_client_readonly),
):
    service_auth.ensure_write_enabled()
    verdict = await HarnessPolicyService.evaluate(payload.action, payload.context, payload.arguments)
    cid = _client_id(client)
    await HarnessAuditService.record(
        "action.evaluated",
        client_id=cid,
        session_no=payload.session_no,
        run_no=payload.run_no,
        actor_type="client",
        actor_id=cid,
        target_type="action",
        target_id=payload.action,
        risk_level=verdict.get("risk_level") or "high",
        decision=verdict.get("decision"),
        policy_code=verdict.get("policy_code"),
        call_id=payload.call_id,
        detail={
            "reason": verdict.get("reason"),
            "tier": verdict.get("tier"),
            "category": verdict.get("category"),
            "command_text": verdict.get("command"),
            "rule_version": verdict.get("rule_version"),
            "ruleset_version": verdict.get("ruleset_version"),
            "signals": verdict.get("signals"),
            "context": payload.context,
        },
    )
    return success_response(data=verdict, msg="评估完成")
