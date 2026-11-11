"""
Harness 会话/运行生命周期服务

- 会话由业务系统创建；run 创建只落业务记录，不做额度预占；
- 计量契约：真实模型用量与额度扣减只由网关（services/gateway）完成；
- 运行结束（成功/失败/取消/超时）只推进状态并写审计事件，不再结算/释放额度；
- `reserved_tokens`/`hold_id` 字段保留但恒为 0/空，供历史数据与看板兼容。
"""
import re
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from packages.common.models.harness import (
    HarnessIdentity,
    HarnessRun,
    HarnessSession,
    HarnessStep,
)
from packages.common.domain.audit_service import HarnessAuditService
from packages.common.domain.identity_service import HarnessIdentityService
from packages.common.domain.policy_service import HarnessPolicyService
from packages.common.domain.pricing_service import ModelPriceService
from packages.common.domain.schemas import SessionCreate

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "timeout"}

# 会话日志文件名：session.v3.jsonl / session.v4.jsonl（可能带 .zstd 后缀）
_SESSION_LOG_RE = re.compile(r"session\.v(\d+)\.jsonl(?:\.zstd)?$", re.IGNORECASE)


def detect_format_version(header: Any) -> Optional[str]:
    """从 JSONL header 的 version 字段推断格式版本（兼容 v3/v4 并存，不写死代际）。"""
    if not isinstance(header, dict):
        return None
    version = header.get("version")
    if version is None or not str(version).strip():
        return None
    text = str(version).strip().lower()
    return text if text.startswith("v") else f"v{text}"


def infer_format_version(path: Optional[str], header: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """优先 header.version；缺失时按 session.v{n}.jsonl 文件名推断。"""
    detected = detect_format_version(header)
    if detected:
        return detected
    if path:
        match = _SESSION_LOG_RE.search(str(path))
        if match:
            return f"v{match.group(1)}"
    return None


def _now() -> datetime:
    return datetime.now()


async def _require_org_active(org_id: int) -> None:
    """组织维度配额：组织必须存在且未停用（P3 fail-closed）。

    走只读 SQL 目录，不注册客户域 ORM 模型（独立服务不能因 FK 拖入 Customer 模型）。
    """
    from packages.common.domain.organization_directory import (
        organization_active,
    )

    if not await organization_active(org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="组织不存在或已停用，拒绝使用组织配额",
        )


async def _resolve_org_member(identity: Optional[HarnessIdentity], org_id: int) -> int:
    """组织会话的成员客户 ID：身份需绑定 customer_id 且为组织活跃成员。"""
    from packages.common.domain.organization_directory import member_active

    meta = identity.meta if identity else None
    customer_id = None
    if isinstance(meta, dict):
        customer_id = meta.get("customer_id") or meta.get("customerId")
    if customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="组织身份未绑定 customer_id，无法落到组织配额账",
        )
    try:
        customer_id = int(customer_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="组织身份 customer_id 非法",
        )
    if not await member_active(org_id, customer_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="客户不是该组织活跃成员，拒绝使用组织配额",
        )
    return customer_id


def _run_metrics(metadata: Optional[Dict[str, Any]], member_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """run.metrics：保留调用方 metadata，并附组织成员维度（供结算写入 usage_record.member_id）。"""
    metrics = dict(metadata or {})
    if member_id is not None:
        metrics["quota_member_id"] = int(member_id)
    return metrics or None


def _declared_org_id(payload: Any) -> Optional[int]:
    """从 metadata/task_payload 提取调用方声明的 org_id（两处声明必须一致）。"""
    found: Optional[int] = None
    for src in (getattr(payload, "metadata", None), getattr(payload, "task_payload", None)):
        if not isinstance(src, dict) or src.get("org_id") is None:
            continue
        try:
            value = int(src["org_id"])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="非法 org_id 声明，拒绝调用",
            )
        if found is not None and value != found:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="metadata 与 task_payload 的 org_id 不一致，拒绝调用",
            )
        found = value
    return found


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def run_to_dict(run: HarnessRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "run_no": run.run_no,
        "session_no": run.session_no,
        "status": run.status,
        "model": run.model,
        "provider": run.provider,
        "estimated_input_tokens": run.estimated_input_tokens,
        "max_output_tokens": run.max_output_tokens,
        "reserved_tokens": run.reserved_tokens,
        "estimated_cost": float(run.estimated_cost or 0),
        "currency": run.currency,
        "hold_id": run.hold_id,
        "output_summary": run.output_summary,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "created_at": _iso(run.created_at),
    }


def session_to_dict(session: HarnessSession) -> Dict[str, Any]:
    return {
        "id": session.id,
        "session_no": session.session_no,
        "client_id": session.client_id,
        "user_id": session.user_id,
        "status": session.status,
        "home_path": session.home_path,
        "cwd": session.cwd,
        "project_key": session.project_key,
        "parent_session_no": session.parent_session_no,
        "runtime_version": session.runtime_version,
        "format_version": session.format_version,
        "session_log_path": session.session_log_path,
        "gateway_key": session.gateway_key,
        "run_count": session.run_count,
        "created_at": _iso(session.created_at),
    }


def step_to_dict(step: HarnessStep) -> Dict[str, Any]:
    return {
        "id": step.id,
        "run_no": step.run_no,
        "node_id": step.node_id,
        "seq": step.seq,
        "step_type": step.step_type,
        "name": step.name,
        "status": step.status,
        "call_id": step.call_id,
        "tokens_in": step.tokens_in,
        "tokens_out": step.tokens_out,
        "cache_read_tokens": step.cache_read_tokens,
        "cache_write_tokens": step.cache_write_tokens,
        "reasoning_tokens": step.reasoning_tokens,
        "total_tokens": step.total_tokens,
        "model": step.model,
        "source": step.source,
        "cost": float(step.cost or 0),
        "raw_seq": step.raw_seq,
        "duration_ms": step.duration_ms,
    }


class HarnessRunService:
    # ---------------- 会话 ----------------
    @classmethod
    async def create_session(cls, payload: SessionCreate, client_id: str) -> HarnessSession:
        if payload.client_id and payload.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="client_id 与凭据不一致")

        identity: Optional[HarnessIdentity] = None
        if payload.external_id:
            identity = await HarnessIdentityService.resolve(
                client_id, payload.external_type, payload.external_id
            )
            if identity is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="外部身份未映射或已禁用",
                )
        user_id = identity.user_id if identity else payload.user_id

        owner_type = identity.owner_type if identity else "usr"
        owner_id = identity.owner_id if identity else user_id
        context = dict(payload.context or {})
        org_member_id: Optional[int] = None
        declared_org = context.get("org_id")
        if owner_type == "org":
            if not owner_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="组织身份缺少 owner_id，拒绝创建会话",
                )
            await _require_org_active(int(owner_id))
            org_member_id = await _resolve_org_member(identity, int(owner_id))
            if declared_org is not None:
                try:
                    declared_org = int(declared_org)
                except (TypeError, ValueError):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="非法 org_id 声明，拒绝创建会话",
                    )
                if declared_org != int(owner_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="跨组织调用被拒绝：context.org_id 与会话归属不一致",
                    )
            context["org_member_customer_id"] = org_member_id
        elif declared_org is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="跨组织调用被拒绝：非组织会话不得声明 org_id",
            )

        if payload.parent_session_no:
            parent = await HarnessSession.get_or_none(session_no=payload.parent_session_no)
            if parent is None or parent.client_id != client_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="父会话不存在")

        session = await HarnessSession.create(
            session_no=f"hs_{secrets.token_hex(12)}",
            client_id=client_id,
            identity_id=identity.id if identity else None,
            user_id=user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            title=payload.title,
            status="open",
            home_path=payload.home_path,
            cwd=payload.cwd,
            project_key=payload.project_key,
            parent_session_no=payload.parent_session_no,
            origin=payload.origin,
            runtime_version=payload.runtime_version,
            format_version=payload.format_version or infer_format_version(payload.session_log_path),
            session_log_path=payload.session_log_path,
            gateway_key=payload.gateway_key,
            context=context or None,
            started_at=_now(),
            last_activity_at=_now(),
        )
        await HarnessAuditService.record(
            "session.created",
            client_id=client_id,
            identity_id=session.identity_id,
            session_no=session.session_no,
            actor_type="client",
            actor_id=client_id,
            target_type="session",
            target_id=session.session_no,
            detail={"title": payload.title, "project_key": payload.project_key},
        )
        return session

    @classmethod
    async def close_session(cls, session_no: str, client_id: str) -> HarnessSession:
        session = await HarnessSession.get_or_none(session_no=session_no)
        if session is None or session.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
        if session.status in ("closed", "expired"):
            return session
        running = await HarnessRun.filter(
            session_no=session_no, status__not_in=list(TERMINAL_STATUSES)
        ).count()
        if running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="会话仍有未结束的运行，请先结束或取消",
            )
        session.status = "closed"
        session.closed_at = _now()
        await session.save()
        # 会话关闭即撤销会话内授权（不做永久放行）
        from packages.common.domain.approval_service import HarnessApprovalService
        revoked = await HarnessApprovalService.revoke_session_grants(session_no)
        await HarnessAuditService.record(
            "session.closed",
            client_id=client_id,
            session_no=session_no,
            target_type="session",
            target_id=session_no,
            detail={"revoked_grants": revoked},
        )
        return session

    # ---------------- 运行 ----------------
    @classmethod
    async def create_run(cls, session_no: str, client_id: str, payload: Any) -> HarnessRun:
        session = await HarnessSession.get_or_none(session_no=session_no)
        if session is None or session.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
        if session.status != "open":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="会话已关闭")

        # ---- P3 组织归属校验：跨组织调用直接拒绝，run 预占落到组织账 ----
        declared_org = _declared_org_id(payload)
        member_id: Optional[int] = None
        if session.owner_type == "org":
            if not session.owner_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="组织会话缺少 owner_id，拒绝创建运行",
                )
            await _require_org_active(int(session.owner_id))
            if declared_org is not None and declared_org != int(session.owner_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="跨组织调用被拒绝：声明 org_id 与会话归属不一致",
                )
            member_id = (session.context or {}).get("org_member_customer_id")
            if member_id is None:
                identity = (
                    await HarnessIdentity.get_or_none(id=session.identity_id)
                    if session.identity_id else None
                )
                member_id = await _resolve_org_member(identity, int(session.owner_id))
                ctx = dict(session.context or {})
                ctx["org_member_customer_id"] = member_id
                session.context = ctx
                await session.save()
            member_id = int(member_id)
            # 成员被移除/停用后不得继续消耗组织配额
            from packages.common.domain.organization_directory import (
                member_active,
            )

            if not await member_active(int(session.owner_id), member_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="客户不是该组织活跃成员，拒绝使用组织配额",
                )
        elif declared_org is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="跨组织调用被拒绝：非组织会话不得声明 org_id",
            )

        run_no = f"hr_{secrets.token_hex(12)}"
        # 计量契约：只有网关写真实用量并扣减额度；编排不再做运行级预占。
        reserved_tokens = 0
        hold_id = ""
        provider = payload.provider or "deepseek"
        price = await ModelPriceService.estimate_cost(
            provider, payload.model,
            input_tokens=payload.estimated_input_tokens or 0,
            output_tokens=payload.max_output_tokens or 0,
        )

        run = await HarnessRun.create(
            run_no=run_no,
            session_no=session_no,
            session_id=session.id,
            client_id=client_id,
            identity_id=session.identity_id,
            user_id=session.user_id,
            owner_type=session.owner_type,
            owner_id=session.owner_id,
            task_type=payload.task_type,
            task_payload=payload.task_payload,
            input_summary=payload.input_summary,
            status="created",
            priority=payload.priority,
            model=payload.model,
            provider=provider,
            estimated_input_tokens=payload.estimated_input_tokens or 0,
            max_output_tokens=payload.max_output_tokens or 0,
            reserved_tokens=reserved_tokens,
            estimated_cost=price["cost"],
            currency=price["currency"],
            price_snapshot=price["price_snapshot"],
            hold_id=None,
            metrics=_run_metrics(payload.metadata, member_id),
            created_by=session.user_id,
        )

        session.run_count = int(session.run_count or 0) + 1
        session.last_activity_at = _now()
        await session.save()

        await HarnessAuditService.record(
            "run.created",
            client_id=client_id,
            identity_id=session.identity_id,
            session_no=session_no,
            run_no=run_no,
            target_type="run",
            target_id=run_no,
            detail={
                "model": payload.model,
                "reserved_tokens": reserved_tokens,
                "hold_id": hold_id,
                "estimated_cost": price["cost"],
            },
        )
        return run

    @classmethod
    async def _get_run(cls, run_no: str, client_id: str) -> HarnessRun:
        run = await HarnessRun.get_or_none(run_no=run_no)
        if run is None or run.client_id != client_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行不存在")
        return run

    @classmethod
    async def start_run(cls, run_no: str, client_id: str) -> HarnessRun:
        run = await cls._get_run(run_no, client_id)
        if run.status in TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="运行已结束")
        run.status = "running"
        run.started_at = run.started_at or _now()
        run.last_heartbeat_at = _now()
        await run.save()
        await HarnessAuditService.record(
            "run.started", client_id=client_id, session_no=run.session_no, run_no=run_no,
        )
        return run

    @classmethod
    async def heartbeat(cls, run_no: str, client_id: str) -> HarnessRun:
        run = await cls._get_run(run_no, client_id)
        if run.status in TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="运行已结束")
        run.last_heartbeat_at = _now()
        await run.save()
        return run

    @classmethod
    async def ingest_step(cls, run_no: str, client_id: str, payload: Any) -> HarnessStep:
        run = await cls._get_run(run_no, client_id)
        if run.status in TERMINAL_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="运行已结束")

        price = await ModelPriceService.estimate_cost(
            payload.provider or run.provider,
            payload.model or run.model,
            input_tokens=payload.tokens_in,
            output_tokens=payload.tokens_out,
            cache_read_tokens=payload.cache_read_tokens,
            cache_write_tokens=payload.cache_write_tokens,
        )
        cost = payload.cost if payload.cost is not None else price["cost"]

        step = await HarnessStep.get_or_none(
            run_id=run.id, node_id=payload.node_id, seq=payload.seq
        )
        fields = dict(
            run_id=run.id,
            run_no=run.run_no,
            session_no=run.session_no,
            node_id=payload.node_id,
            seq=payload.seq,
            step_type=payload.step_type,
            name=payload.name,
            status=payload.status,
            call_id=payload.call_id,
            input=payload.input,
            output=payload.output,
            tokens_in=payload.tokens_in,
            tokens_out=payload.tokens_out,
            cache_read_tokens=payload.cache_read_tokens,
            cache_write_tokens=payload.cache_write_tokens,
            reasoning_tokens=payload.reasoning_tokens,
            total_tokens=payload.total_tokens,
            model=payload.model or run.model,
            provider=payload.provider or run.provider,
            source=payload.source,
            cost=cost,
            price_snapshot=price["price_snapshot"],
            raw_seq=payload.raw_seq,
            started_at=datetime.fromisoformat(payload.started_at) if payload.started_at else None,
            finished_at=datetime.fromisoformat(payload.finished_at) if payload.finished_at else None,
            duration_ms=payload.duration_ms,
        )
        if step is None:
            step = await HarnessStep.create(**fields)
        else:
            for key, value in fields.items():
                setattr(step, key, value)
            await step.save()

        run.last_heartbeat_at = _now()
        await run.save()

        # 工具调用/审批类事件写入安全审计（callId 关联 tool/call 与 approval/asked）
        if payload.step_type in ("tool_call", "tool_result", "approval", "compaction", "action"):
            decision = None
            policy_code = None
            if payload.step_type in ("tool_call", "action"):
                verdict = await HarnessPolicyService.evaluate(
                    payload.name or payload.step_type,
                    {"client_id": client_id, "session_no": run.session_no},
                    payload.input,
                )
                decision = verdict.get("decision")
                policy_code = verdict.get("policy_code")
            await HarnessAuditService.record(
                f"step.{payload.step_type}",
                client_id=client_id,
                session_no=run.session_no,
                run_no=run.run_no,
                step_id=step.id,
                target_type="tool" if payload.step_type.startswith("tool") else "step",
                target_id=payload.name,
                risk_level="high" if payload.step_type == "action" else "medium",
                decision=decision,
                policy_code=policy_code,
                call_id=payload.call_id,
                raw_seq=payload.raw_seq,
                detail={"name": payload.name, "status": payload.status},
            )
        return step

    @classmethod
    async def complete_run(cls, run_no: str, client_id: str, payload: Any) -> HarnessRun:
        run = await cls._get_run(run_no, client_id)
        if run.status in TERMINAL_STATUSES:
            return run

        final_status = payload.status if payload.status in TERMINAL_STATUSES else "succeeded"
        # 计量契约：真实用量与额度扣减只由网关完成；编排只推进状态与写审计。
        run.status = final_status
        run.output_summary = payload.output_summary
        run.error_code = payload.error_code
        run.error_message = payload.error_message
        run.finished_at = _now()
        await run.save()

        session = await HarnessSession.get_or_none(session_no=run.session_no)
        if session is not None:
            session.last_activity_at = _now()
            await session.save()

        await HarnessAuditService.record(
            f"run.{final_status}",
            client_id=client_id,
            identity_id=run.identity_id,
            session_no=run.session_no,
            run_no=run.run_no,
            target_type="run",
            target_id=run.run_no,
            risk_level="low" if final_status == "succeeded" else "medium",
            detail={"error_code": payload.error_code, "usage_entries": len(payload.usage or [])},
        )
        return run

    @classmethod
    async def cancel_run(cls, run_no: str, client_id: str, reason: Optional[str] = None) -> HarnessRun:
        run = await cls._get_run(run_no, client_id)
        if run.status in TERMINAL_STATUSES:
            return run
        # 计量契约：额度由网关按请求扣减，编排取消运行无需释放预占。
        run.status = "cancelled"
        run.error_code = "cancelled"
        run.error_message = reason
        run.finished_at = _now()
        await run.save()
        await HarnessAuditService.record(
            "run.cancelled", client_id=client_id, session_no=run.session_no, run_no=run.run_no,
            risk_level="medium", detail={"reason": reason},
        )
        return run
