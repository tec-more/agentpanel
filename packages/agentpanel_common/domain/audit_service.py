"""Harness 审计事件服务（事件编号 + 请求上下文留痕）"""
import secrets
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Request

from packages.agentpanel_common.models.harness import HarnessAuditEvent


class HarnessAuditService:
    @classmethod
    async def record(
        cls,
        action: str,
        *,
        client_id: Optional[str] = None,
        identity_id: Optional[int] = None,
        session_no: Optional[str] = None,
        run_no: Optional[str] = None,
        step_id: Optional[int] = None,
        actor_type: str = "client",
        actor_id: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        risk_level: str = "low",
        decision: Optional[str] = None,
        policy_code: Optional[str] = None,
        call_id: Optional[str] = None,
        raw_seq: int = 0,
        event_source: str = "api",
        raw_type: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
        trace_id: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> HarnessAuditEvent:
        ip = None
        user_agent = None
        request_id = None
        if request is not None:
            ip = request.client.host if request.client else None
            user_agent = request.headers.get("User-Agent")
            request_id = request.headers.get("X-Request-Id")
            trace_id = trace_id or request.headers.get("X-Trace-Id")

        return await HarnessAuditEvent.create(
            event_no=f"hae_{secrets.token_hex(12)}",
            client_id=client_id,
            identity_id=identity_id,
            session_no=session_no,
            run_no=run_no,
            step_id=step_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            risk_level=risk_level,
            decision=decision,
            policy_code=policy_code,
            call_id=call_id,
            raw_seq=raw_seq,
            event_source=event_source,
            raw_type=raw_type,
            detail=detail,
            request_id=request_id,
            trace_id=trace_id,
            ip_address=ip,
            user_agent=user_agent,
            occurred_at=occurred_at or datetime.now(),
        )
