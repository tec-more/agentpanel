"""Harness 审计事件：客户端上报 + 管理员查询"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from base.common.permissions import require_superuser
from base.common.response import success_response
from base.plugins.harness.models.harness import HarnessAuditEvent
from base.plugins.harness.schemas.harness import AuditIngest
from base.plugins.harness.services.audit_service import HarnessAuditService
from base.plugins.harness.services.client_service import require_harness_client

audit_router = APIRouter(prefix="/audit-events", tags=["Harness-审计"])


def _event_dict(row: HarnessAuditEvent) -> dict:
    return {
        "id": row.id,
        "event_no": row.event_no,
        "client_id": row.client_id,
        "session_no": row.session_no,
        "run_no": row.run_no,
        "step_id": row.step_id,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "action": row.action,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "risk_level": row.risk_level,
        "decision": row.decision,
        "policy_code": row.policy_code,
        "call_id": row.call_id,
        "raw_seq": row.raw_seq,
        "event_source": row.event_source,
        "raw_type": row.raw_type,
        "detail": row.detail,
        "trace_id": row.trace_id,
        "ip_address": row.ip_address,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@audit_router.post("", summary="上报 Harness 审计事件")
async def ingest_event(
    payload: AuditIngest,
    request: Request,
    client=Depends(require_harness_client),
):
    event = await HarnessAuditService.record(
        payload.action,
        client_id=client.client_id,
        session_no=payload.session_no,
        run_no=payload.run_no,
        step_id=payload.step_id,
        actor_type="client",
        actor_id=client.client_id,
        risk_level=payload.risk_level,
        decision=payload.decision,
        policy_code=payload.policy_code,
        call_id=payload.call_id,
        raw_seq=payload.raw_seq,
        detail=payload.detail,
        request=request,
        trace_id=payload.trace_id,
    )
    return success_response(data=_event_dict(event), msg="事件已记录")


@audit_router.get("", summary="审计事件分页查询（管理员）")
async def list_events(
    client_id: Optional[str] = Query(None),
    session_no: Optional[str] = Query(None),
    run_no: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None, description="tool/approval/policy"),
    target_id: Optional[str] = Query(None, description="工具名/审批单号等"),
    decision: Optional[str] = Query(None, description="allow/deny/ask/approved/denied"),
    risk_level: Optional[str] = Query(None),
    call_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    query = HarnessAuditEvent.all()
    if client_id:
        query = query.filter(client_id=client_id)
    if session_no:
        query = query.filter(session_no=session_no)
    if run_no:
        query = query.filter(run_no=run_no)
    if action:
        query = query.filter(action=action)
    if target_type:
        query = query.filter(target_type=target_type)
    if target_id:
        query = query.filter(target_id=target_id)
    if decision:
        query = query.filter(decision=decision)
    if risk_level:
        query = query.filter(risk_level=risk_level)
    if call_id:
        query = query.filter(call_id=call_id)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size).order_by("-occurred_at", "-id")
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_event_dict(r) for r in rows],
    })
