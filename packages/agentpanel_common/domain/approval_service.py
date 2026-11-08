"""
审批联动服务（三档策略，fail-closed）

拦截点（本实现选择 backend_api，后端侧挡）：
- dsh 0.1.5rc1 SDK profile 未注册审批通道，session/request_permission 不会下发，
  approval/decided 直接 unavailable，因此不能依赖 dsh 审批通道；
- 本服务在 Harness 后端对 tool/call 做策略判定：allow 直接放行、deny 直接拒绝、
  ask 落审批单等待人工决策；审批结果由业务侧回写 `approval/{approval_no}/decision`。
- 后端侧挡的边界：判定、审批单、审计由本服务保证权威性；业务调用方在拿不到 allow
  之前不得继续下发该 tool/action。仍保留 dsh workspace-write 沙箱，不注入
  danger-full-access；danger-full-access 视为风险升级，必定转人工。
- 验证边界（本机 Windows 已验）：三档分级、白/黑名单命中、转人工落单、300 秒超时拒绝、
  once/session_pattern 授权、审批人校验、审计字段、会话关闭撤销授权。
- 待 Linux 容器验证：dsh 进程内执行前的硬拦截（本机 pwsh-sandbox 执行器报
  `--profile <name> is required`）、workspace 越界写/出网的实际阻断、
  dsh 原生 approval/decided 通道（0.1.5rc1 SDK profile 未注册审批通道）。

默认值：
- 审批超时 300 秒，超时按拒绝处理（fail-closed）；
- 授权粒度默认 once（仅本次），另支持 session_pattern（本会话内同一命令模式），
  不做永久放行；会话关闭即撤销授权；
- 审批人默认本次任务发起人；高危（high/critical）与跨租户请求由组织管理员兜底；
- asked 与 decided 均写审计，含命令原文、发起人、审批人、理由、超时时间。
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from packages.agentpanel_common.models.harness import (
    HarnessApprovalGrant,
    HarnessApprovalRequest,
    HarnessRun,
    HarnessSession,
    HarnessStep,
)
from packages.agentpanel_common.domain.audit_service import HarnessAuditService
from packages.agentpanel_common.domain.policy_rule_service import command_pattern_of
from packages.agentpanel_common.domain.policy_service import HarnessPolicyService, approval_config
from packages.agentpanel_common.domain.run_service import TERMINAL_STATUSES
from packages.agentpanel_common.domain.user_directory import UserRef, first_admin, resolve_user

APPROVAL_ACTION = "approval.asked"
DECIDED_ACTION = "approval.decided"
AUTO_GRANT_ACTION = "approval.auto_granted"


def _now() -> datetime:
    """与 Tortoise use_tz=True 对齐，统一使用带时区时间，避免超时比较报错。"""
    return datetime.now(timezone.utc)


class HarnessApprovalService:
    # ---------------- 审批请求 ----------------
    @classmethod
    async def request(cls, client_id: str, payload: Any) -> Dict[str, Any]:
        run = await HarnessRun.get_or_none(run_no=payload.run_no)
        if run is None or run.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行不存在")
        if run.status in TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="运行已结束")

        arguments = payload.arguments
        if arguments is None and payload.call_id:
            step = await HarnessStep.filter(
                run_id=run.id, call_id=payload.call_id, step_type="tool_call",
            ).order_by("seq").first()
            arguments = step.input if step else None

        context = dict(payload.context or {})
        context.update({
            "run_no": run.run_no,
            "session_no": run.session_no,
            "call_id": payload.call_id,
            "user_id": run.user_id,
        })
        verdict = await HarnessPolicyService.evaluate(payload.action, context, arguments)
        cfg = approval_config()

        approval_no = None
        approval = None
        auto_granted = False
        if verdict["decision"] == "ask":
            # 会话内同一命令模式授权命中 → 自动放行（不重复打扰人）
            grant = await cls._find_grant(
                run.session_no, verdict.get("command_pattern"),
            )
            if grant is not None:
                grant.uses = (grant.uses or 0) + 1
                grant.expires_at = None
                await grant.save()
                auto_granted = True
                await HarnessAuditService.record(
                    AUTO_GRANT_ACTION,
                    client_id=client_id,
                    identity_id=run.identity_id,
                    session_no=run.session_no,
                    run_no=run.run_no,
                    call_id=payload.call_id,
                    actor_type="system",
                    actor_id="policy",
                    target_type="action",
                    target_id=payload.action,
                    risk_level=verdict.get("risk_level") or "medium",
                    decision="allow",
                    policy_code=verdict.get("policy_code"),
                    event_source="api",
                    raw_type=AUTO_GRANT_ACTION,
                    detail={
                        "approval_no": grant.approval_no,
                        "scope": "session_pattern",
                        "pattern": grant.pattern,
                        "command_text": verdict.get("command"),
                        "initiator_user_id": run.user_id,
                        "rule_version": verdict.get("rule_version"),
                        "ruleset_version": verdict.get("ruleset_version"),
                    },
                )
            else:
                approval = await cls._create_request(
                    client_id, run, payload, arguments, verdict, context, cfg,
                )
                approval_no = approval.approval_no

        decision = "allow" if auto_granted else verdict["decision"]
        audit_action = APPROVAL_ACTION if decision == "ask" else "approval.requested"
        detail = {
            "approval_no": approval_no,
            "reason": verdict.get("reason"),
            "command_text": verdict.get("command"),
            "command_pattern": verdict.get("command_pattern"),
            "policy_code": verdict.get("policy_code"),
            "tier": verdict.get("tier"),
            "rule_version": verdict.get("rule_version"),
            "ruleset_version": verdict.get("ruleset_version"),
            "signals": verdict.get("signals"),
            "tool_arguments": arguments,
        }
        if approval is not None:
            detail.update({
                "initiator_user_id": approval.initiator_user_id,
                "approver_user_id": approval.approver_user_id,
                "approver_role": approval.approver_role,
                "timeout_seconds": approval.timeout_seconds,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                "scope": approval.scope,
                "pattern": approval.pattern,
            })
        if not auto_granted:
            await HarnessAuditService.record(
                audit_action,
                client_id=client_id,
                identity_id=run.identity_id,
                session_no=run.session_no,
                run_no=run.run_no,
                call_id=payload.call_id,
                actor_type="client",
                actor_id=payload.requested_by or client_id,
                target_type="action",
                target_id=payload.action,
                risk_level=verdict.get("risk_level") or "high",
                decision=decision,
                policy_code=verdict.get("policy_code"),
                event_source="api",
                raw_type=audit_action,
                detail=detail,
            )

        return {
            "approval_no": approval_no,
            "decision": decision,
            "reason": verdict.get("reason"),
            "policy_code": verdict.get("policy_code"),
            "risk_level": verdict.get("risk_level"),
            "tier": verdict.get("tier"),
            "category": verdict.get("category"),
            "command_text": verdict.get("command"),
            "command_pattern": verdict.get("command_pattern"),
            "signals": verdict.get("signals"),
            "rule_version": verdict.get("rule_version"),
            "ruleset_version": verdict.get("ruleset_version"),
            "interception": verdict.get("interception"),
            "requires_approval": approval is not None,
            "auto_granted": auto_granted,
            "initiator_user_id": approval.initiator_user_id if approval else run.user_id,
            "approver_user_id": approval.approver_user_id if approval else None,
            "approver_role": approval.approver_role if approval else None,
            "scope": approval.scope if approval else None,
            "pattern": approval.pattern if approval else None,
            "timeout_seconds": approval.timeout_seconds if approval else None,
            "expires_at": approval.expires_at.isoformat() if approval and approval.expires_at else None,
            "tool_arguments": arguments,
        }

    @classmethod
    async def _create_request(
        cls,
        client_id: str,
        run: HarnessRun,
        payload: Any,
        arguments: Any,
        verdict: Dict[str, Any],
        context: Dict[str, Any],
        cfg: Dict[str, Any],
    ) -> HarnessApprovalRequest:
        # 同一 run + callId 重复上报时复用未决单，避免重复打扰
        if payload.call_id:
            existing = await HarnessApprovalRequest.filter(
                client_id=client_id, run_no=run.run_no, call_id=payload.call_id,
                action=payload.action, status="pending",
            ).order_by("-id").first()
            if existing is not None and existing.expires_at and existing.expires_at > _now():
                return existing

        initiator_user_id = run.user_id
        if initiator_user_id is None:
            session = await HarnessSession.get_or_none(session_no=run.session_no)
            initiator_user_id = session.user_id if session else None

        cross_tenant = bool(context.get("cross_tenant") or context.get("cross_tenant_id"))
        risk_level = (verdict.get("risk_level") or "medium").lower()
        admin_fallback_risk = [str(r).lower() for r in cfg["admin_fallback_risk"]]
        if cross_tenant or risk_level in admin_fallback_risk:
            approver_role = "admin"
            admin = await cls._admin_user()
            approver_user_id = admin.id if admin else None
        else:
            approver_role = "initiator"
            approver_user_id = initiator_user_id
            if approver_user_id is None:
                approver_role = "admin"
                admin = await cls._admin_user()
                approver_user_id = admin.id if admin else None

        timeout_seconds = int(cfg["timeout_seconds"])
        requested_at = _now()
        approval_no = f"hap_{secrets.token_hex(10)}"
        return await HarnessApprovalRequest.create(
            approval_no=approval_no,
            client_id=client_id,
            run_no=run.run_no,
            session_no=run.session_no,
            action=payload.action,
            call_id=payload.call_id,
            command_text=verdict.get("command"),
            initiator_user_id=initiator_user_id,
            approver_user_id=approver_user_id,
            approver_role=approver_role,
            risk_level=risk_level,
            policy_code=verdict.get("policy_code"),
            reason=verdict.get("reason"),
            scope=cfg["default_scope"],
            pattern=verdict.get("command_pattern"),
            status="pending",
            timeout_seconds=timeout_seconds,
            requested_at=requested_at,
            expires_at=requested_at + timedelta(seconds=timeout_seconds),
            detail={
                "tier": verdict.get("tier"),
                "category": verdict.get("category"),
                "signals": verdict.get("signals"),
                "rule_version": verdict.get("rule_version"),
                "ruleset_version": verdict.get("ruleset_version"),
                "interception": verdict.get("interception"),
                "cross_tenant": cross_tenant,
                "tool_arguments": arguments,
            },
        )

    # ---------------- 审批决策 ----------------
    @classmethod
    async def decide(cls, client_id: str, approval_no: str, payload: Any) -> Dict[str, Any]:
        approval = await HarnessApprovalRequest.get_or_none(approval_no=approval_no)
        if approval is None or approval.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审批单不存在")

        # 超时后即使收到 approved 也按拒绝处理（fail-closed）
        if approval.status == "pending" and approval.expires_at and approval.expires_at <= _now():
            await cls._expire(approval)
        if approval.status != "pending":
            return cls._record_dict(approval)

        decider = await cls._resolve_user(getattr(payload, "approver", None))
        if decider is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="approver 必填且必须是有效用户",
            )
        if not decider.is_superuser:
            if approval.approver_role == "admin":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="高危/跨租户审批需组织管理员")
            expected = approval.approver_user_id or approval.initiator_user_id
            if expected and decider.id != expected:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅指定审批人可决策")

        raw = (payload.decision or "").lower()
        if raw in ("approved", "allow", "allowed", "true"):
            decision = "allow"
        elif raw in ("denied", "deny", "rejected", "false"):
            decision = "deny"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="decision 仅支持 approved/denied",
            )

        cfg = approval_config()
        scope = (getattr(payload, "scope", None) or cfg["default_scope"]).lower()
        if scope not in cfg["allowed_scopes"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scope 仅支持 " + "/".join(cfg["allowed_scopes"]),
            )
        pattern = None
        if decision == "allow" and scope == "session_pattern":
            pattern = (
                getattr(payload, "pattern", None)
                or approval.pattern
                or command_pattern_of(approval.command_text)
                or approval.action
            )[:200]

        approval.status = "approved" if decision == "allow" else "denied"
        approval.decision = decision
        approval.scope = scope
        approval.pattern = pattern
        approval.decided_at = _now()
        approval.decided_by = str(decider.id)
        approval.comment = payload.comment
        await approval.save()

        if decision == "allow" and scope == "session_pattern" and pattern:
            await cls._grant(approval, pattern)

        reason = payload.comment or (
            f"approved_by:{decider.username}" if decision == "allow" else f"denied_by:{decider.username}"
        )
        await HarnessAuditService.record(
            DECIDED_ACTION,
            client_id=client_id,
            identity_id=None,
            session_no=approval.session_no,
            run_no=approval.run_no,
            call_id=approval.call_id,
            actor_type="user",
            actor_id=str(decider.id),
            target_type="approval",
            target_id=approval.approval_no,
            risk_level=approval.risk_level,
            decision=decision,
            policy_code=approval.policy_code,
            event_source="api",
            raw_type=DECIDED_ACTION,
            detail={
                "approval_no": approval.approval_no,
                "command_text": approval.command_text,
                "command_pattern": approval.pattern,
                "initiator_user_id": approval.initiator_user_id,
                "approver_user_id": decider.id,
                "approver_username": decider.username,
                "approver_role": approval.approver_role,
                "reason": reason,
                "decision_raw": raw,
                "timeout_seconds": approval.timeout_seconds,
                "scope": scope,
            },
        )
        return cls._record_dict(approval)

    # ---------------- 超时 / 查询 ----------------
    @classmethod
    async def expire_pending(cls, client_id: Optional[str] = None) -> int:
        query = HarnessApprovalRequest.filter(status="pending", expires_at__lte=_now())
        if client_id:
            query = query.filter(client_id=client_id)
        rows = await query.all()
        for row in rows:
            await cls._expire(row)
        return len(rows)

    @classmethod
    async def _expire(cls, approval: HarnessApprovalRequest) -> None:
        if approval.status != "pending":
            return
        approval.status = "expired"
        approval.decision = "deny"
        approval.decided_at = _now()
        approval.decided_by = "system"
        approval.comment = approval.comment or "approval_timeout"
        await approval.save()
        await HarnessAuditService.record(
            DECIDED_ACTION,
            client_id=approval.client_id,
            session_no=approval.session_no,
            run_no=approval.run_no,
            call_id=approval.call_id,
            actor_type="system",
            actor_id="timeout",
            target_type="approval",
            target_id=approval.approval_no,
            risk_level=approval.risk_level,
            decision="deny",
            policy_code=approval.policy_code,
            event_source="api",
            raw_type=DECIDED_ACTION,
            detail={
                "approval_no": approval.approval_no,
                "command_text": approval.command_text,
                "initiator_user_id": approval.initiator_user_id,
                "approver_user_id": approval.approver_user_id,
                "reason": "approval_timeout",
                "timeout_seconds": approval.timeout_seconds,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                "scope": approval.scope,
            },
        )

    @classmethod
    async def pending(cls, client_id: str, approver: Optional[str] = None) -> List[Dict[str, Any]]:
        await cls.expire_pending(client_id)
        query = HarnessApprovalRequest.filter(client_id=client_id, status="pending")
        if approver:
            user = await cls._resolve_user(approver)
            if user is not None and not user.is_superuser:
                query = query.filter(approver_user_id=user.id)
        rows = await query.order_by("expires_at", "-id").all()
        return [cls._record_dict(row) for row in rows]

    # ---------------- 授权粒度 ----------------
    @classmethod
    async def _find_grant(cls, session_no: Optional[str], pattern: Optional[str]) -> Optional[HarnessApprovalGrant]:
        if not session_no or not pattern:
            return None
        return await HarnessApprovalGrant.get_or_none(
            session_no=session_no, pattern=pattern[:200], status="active",
        )

    @classmethod
    async def _grant(cls, approval: HarnessApprovalRequest, pattern: str) -> HarnessApprovalGrant:
        grant = await HarnessApprovalGrant.get_or_none(
            session_no=approval.session_no, pattern=pattern,
        )
        if grant is None:
            return await HarnessApprovalGrant.create(
                approval_no=approval.approval_no,
                client_id=approval.client_id,
                session_no=approval.session_no,
                pattern=pattern,
                scope="session_pattern",
                status="active",
                uses=0,
            )
        grant.approval_no = approval.approval_no
        grant.status = "active"
        grant.scope = "session_pattern"
        await grant.save()
        return grant

    @classmethod
    async def revoke_session_grants(cls, session_no: str) -> int:
        """会话关闭时撤销全部会话内授权（不做永久放行）。"""
        grants = await HarnessApprovalGrant.filter(session_no=session_no, status="active").all()
        for grant in grants:
            grant.status = "revoked"
            grant.expires_at = _now()
            await grant.save()
        return len(grants)

    # ---------------- 工具 ----------------
    @staticmethod
    async def _resolve_user(identifier: Any) -> Optional[UserRef]:
        return await resolve_user(identifier)

    @staticmethod
    async def _admin_user() -> Optional[UserRef]:
        return await first_admin()

    @staticmethod
    def _record_dict(row: HarnessApprovalRequest) -> Dict[str, Any]:
        return {
            "approval_no": row.approval_no,
            "client_id": row.client_id,
            "run_no": row.run_no,
            "session_no": row.session_no,
            "action": row.action,
            "call_id": row.call_id,
            "command_text": row.command_text,
            "pattern": row.pattern,
            "initiator_user_id": row.initiator_user_id,
            "approver_user_id": row.approver_user_id,
            "approver_role": row.approver_role,
            "risk_level": row.risk_level,
            "policy_code": row.policy_code,
            "reason": row.reason,
            "scope": row.scope,
            "status": row.status,
            "decision": row.decision,
            "timeout_seconds": row.timeout_seconds,
            "requested_at": row.requested_at.isoformat() if row.requested_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "decided_by": row.decided_by,
            "comment": row.comment,
            "detail": row.detail,
        }
