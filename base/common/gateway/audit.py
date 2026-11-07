"""网关审计：写入 HarnessAuditEvent（event_source=gateway），不写业务 audit_log。"""
from typing import Any, Dict, Optional

from fastapi import Request

from base.common.gateway.constants import GATEWAY_EVENT_SOURCE
from base.common.gateway.logging import gateway_logger


async def record_gateway_auth_reject(
    request: Request,
    *,
    reason: str,
    token_kind: str,
    status_code: int = 401,
) -> None:
    """记录鉴权拒绝事件；只记原因与凭据类型，绝不落 token 本身。"""
    try:
        from base.plugins.harness.services.audit_service import HarnessAuditService

        await HarnessAuditService.record(
            "gateway.auth_rejected",
            target_type="gateway_endpoint",
            target_id=str(request.url.path)[:128],
            risk_level="medium",
            decision="deny",
            event_source=GATEWAY_EVENT_SOURCE,
            detail={
                "reason": reason,
                "token_kind": token_kind,
                "status": status_code,
                "method": request.method,
            },
            request=request,
        )
    except Exception as exc:
        # 审计失败不得影响拒绝响应本身
        gateway_logger.warning(f"[gateway] 鉴权拒绝审计写入失败: {type(exc).__name__}")


async def record_gateway_quota_event(
    *,
    action: str,
    lease_id: str,
    reason: str,
    detail: Optional[Dict[str, Any]] = None,
    risk_level: str = "medium",
    decision: str = "deny",
    client_id: Optional[str] = None,
    session_no: Optional[str] = None,
    run_no: Optional[str] = None,
    actor_type: str = "system",
    actor_id: str = "gateway-budget",
) -> None:
    """额度拒绝/流式截断/吊销事件；不写 prompt/正文，只留额度元数据。"""
    try:
        from base.plugins.harness.services.audit_service import HarnessAuditService

        payload = {"lease_id": lease_id, "reason": reason}
        if detail:
            payload.update(detail)
        await HarnessAuditService.record(
            action,
            client_id=client_id,
            session_no=session_no,
            run_no=run_no,
            actor_type=actor_type,
            actor_id=actor_id,
            target_type="gateway_lease",
            target_id=lease_id,
            risk_level=risk_level,
            decision=decision,
            event_source=GATEWAY_EVENT_SOURCE,
            detail=payload,
        )
    except Exception as exc:
        gateway_logger.warning(f"[gateway] 额度审计写入失败 action={action}: {type(exc).__name__}")
