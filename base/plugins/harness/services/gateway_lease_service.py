"""
Harness 网关虚拟 key 租约服务（控制面）

安全约定：
- 虚拟 key 明文只在签发响应中出现一次；DB 只存 SHA-256 与 12 位指纹；
- 租约绑定 client / session / run 与配额主体（owner_type/owner_id/member_id）；
- 分钟级过期、可续期、可吊销、按租约 RPM 限流；
- 复用 HarnessClient 凭据体系，不另起一套客户端账号。
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from base.plugins.harness.services.gateway_config import issuance_config, lease_ttl_override
from services.gateway.gateway.lease_auth import (
    TERMINAL_RUN_STATUSES,
    VIRTUAL_KEY_PREFIX,
    authenticate as validate_gateway_lease,
    invalidate_lease_cache,
)
from base.common.quota.models.quota import QuotaAccount
from base.plugins.harness.models.harness import (
    HarnessGatewayLease,
    HarnessRun,
    HarnessSession,
)
from base.plugins.harness.services.client_service import hash_secret


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: Optional[datetime]) -> Optional[str]:
    """统一按 UTC 输出，避免 use_tz 下本地时区/UTC 混排。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _ttl_seconds(
    value: Optional[int],
    default_key: str,
    *,
    owner_type: Optional[str] = None,
    owner_id: Optional[int] = None,
) -> int:
    """TTL 解析：显式请求 > 租户覆盖 > 全局默认，最终夹到 [30, max_lease_ttl_seconds]。"""
    cfg = issuance_config()
    default = int(cfg.get(default_key) or 900)
    override = lease_ttl_override(cfg, owner_type, owner_id)
    base = int(override) if override is not None else default
    max_ttl = int(cfg.get("max_lease_ttl_seconds") or 3600)
    ttl = int(value or base)
    if ttl < 30:
        ttl = 30
    return min(ttl, max_ttl)


def _virtual_key(lease_id: str) -> str:
    secret = secrets.token_urlsafe(32)
    return f"{VIRTUAL_KEY_PREFIX}.{lease_id}.{secret}"


class GatewayLeaseService:
    """租约签发/续期/吊销/鉴权（控制面与数据面共用鉴权逻辑）"""

    # ---------------- 签发 ----------------
    @classmethod
    async def issue(
        cls,
        client,
        *,
        session_no: Optional[str] = None,
        run_no: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        rpm_limit: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        budget_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        cfg = issuance_config()
        rpm = int(rpm_limit or cfg.get("max_rpm") or 60)
        if rpm <= 0:
            raise HTTPException(status_code=400, detail="rpm_limit 必须为正整数")

        session: Optional[HarnessSession] = None
        if session_no:
            session = await HarnessSession.get_or_none(session_no=session_no)
            if session is None or session.client_id != client.client_id:
                raise HTTPException(status_code=404, detail="会话不存在或不属于该客户端")
            if session.status != "open":
                raise HTTPException(status_code=409, detail="会话已关闭，不能签发网关租约")

        run: Optional[HarnessRun] = None
        if run_no:
            run = await HarnessRun.get_or_none(run_no=run_no)
            if run is None or run.client_id != client.client_id:
                raise HTTPException(status_code=404, detail="运行不存在或不属于该客户端")
            if session and run.session_no != session.session_no:
                raise HTTPException(status_code=409, detail="run 与 session 归属不一致")
            if run.status in TERMINAL_RUN_STATUSES:
                raise HTTPException(status_code=409, detail="运行已结束，不能签发网关租约")
            if session is None and run.session_no:
                session = await HarnessSession.get_or_none(session_no=run.session_no)

        owner_type = session.owner_type if session else (run.owner_type if run else "usr")
        owner_id = session.owner_id if session else (run.owner_id if run else None)
        # 租户覆盖需要先解析租户归属；显式 ttl_seconds 仍优先级最高
        ttl = _ttl_seconds(
            ttl_seconds,
            "lease_ttl_seconds",
            owner_type=owner_type,
            owner_id=owner_id,
        )
        member_id = None
        if owner_type == "org" and session is not None:
            member_id = (session.context or {}).get("org_member_customer_id")
        provider_name = provider or (run.provider if run else None)
        model_name = model or (run.model if run else None)

        lease_id = f"gl_{secrets.token_hex(12)}"
        key = _virtual_key(lease_id)
        key_hash = hash_secret(key.split(".", 2)[2])
        now = _now()
        lease = await HarnessGatewayLease.create(
            lease_id=lease_id,
            key_hash=key_hash,
            key_prefix=f"{VIRTUAL_KEY_PREFIX}.{lease_id}",
            key_fingerprint=key_hash[:12],
            client_id=client.client_id,
            session_no=session.session_no if session else (run.session_no if run else None),
            run_no=run.run_no if run else None,
            owner_type=owner_type,
            owner_id=owner_id,
            member_id=member_id,
            provider=provider_name,
            model=model_name,
            status="active",
            expires_at=now + timedelta(seconds=ttl),
            rpm_limit=rpm,
            meta={
                "issued_by": client.client_id,
                "session_no": session.session_no if session else None,
                "run_no": run.run_no if run else None,
                "ttl_seconds": ttl,
                "budget_tokens": int(budget_tokens) if budget_tokens is not None else None,
            },
        )
        return {
            "lease_id": lease.lease_id,
            "virtual_key": key,
            "key_fingerprint": lease.key_fingerprint,
            "expires_at": _iso_utc(lease.expires_at),
            "ttl_seconds": ttl,
            "renew_after_seconds": int(ttl * 0.8),
            "rpm_limit": rpm,
            "base_url": str(cfg.get("public_base_url") or "").rstrip("/"),
            "provider": lease.provider,
            "model": lease.model,
            "session_no": lease.session_no,
            "run_no": lease.run_no,
            "owner_type": lease.owner_type,
            "owner_id": lease.owner_id,
            "member_id": lease.member_id,
        }

    # ---------------- 续期 / 吊销 ----------------
    @classmethod
    async def _audit_renew_failed(
        cls,
        lease: Optional[HarnessGatewayLease],
        *,
        reason: str,
        status_code: int,
        client_id: Optional[str] = None,
    ) -> None:
        from services.gateway.gateway.audit import record_gateway_quota_event

        await record_gateway_quota_event(
            action="gateway.lease_renew_failed",
            lease_id=(lease.lease_id if lease else "unknown"),
            reason=reason,
            detail={"status": status_code},
            risk_level="high",
            decision="deny",
            client_id=(lease.client_id if lease else client_id),
            session_no=(lease.session_no if lease else None),
            run_no=(lease.run_no if lease else None),
            actor_type="client",
            actor_id=client_id or (lease.client_id if lease else None) or "gateway-lease",
        )

    @classmethod
    async def _mark_invalid(
        cls,
        lease: HarnessGatewayLease,
        reason: str,
    ) -> None:
        """续期失败降级：标记失效 + 写穿缓存；不触碰任何在途流。"""
        lease.status = "invalid"
        lease.invalidated_at = _now()
        lease.invalid_reason = reason[:100]
        await lease.save(
            update_fields=["status", "invalidated_at", "invalid_reason", "updated_at"]
        )
        await invalidate_lease_cache(lease.lease_id)

    @classmethod
    async def renew(
        cls,
        lease_id: str,
        client,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        from services.gateway.gateway.budget import GatewayBudgetService

        client_id = getattr(client, "client_id", None) or str(client)
        client_status = getattr(client, "status", "active") or "active"

        lease = await HarnessGatewayLease.get_or_none(lease_id=lease_id)
        if lease is None or lease.client_id != client_id:
            await cls._audit_renew_failed(
                None, reason="lease_not_found", status_code=404, client_id=client_id
            )
            raise HTTPException(status_code=404, detail="租约不存在或不属于该客户端")

        if lease.status == "revoked":
            await cls._audit_renew_failed(lease, reason="lease_revoked", status_code=409)
            raise HTTPException(status_code=409, detail="租约已吊销")
        if lease.status == "invalid":
            await cls._audit_renew_failed(lease, reason="lease_invalid", status_code=409)
            raise HTTPException(status_code=409, detail="租约已失效")
        if lease.status != "active":
            await cls._audit_renew_failed(
                lease, reason=f"lease_status_{lease.status}", status_code=409
            )
            raise HTTPException(status_code=409, detail="租约状态不可续期")

        expires = lease.expires_at
        if expires is not None:
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= _now():
                await cls._mark_invalid(lease, "lease_expired")
                await cls._audit_renew_failed(
                    lease, reason="lease_expired", status_code=409
                )
                raise HTTPException(status_code=409, detail="租约已过期，不能续期")

        if client_status != "active":
            await cls._mark_invalid(lease, "client_disabled")
            await cls._audit_renew_failed(
                lease, reason="client_disabled", status_code=403
            )
            raise HTTPException(status_code=403, detail="客户端已停用，租约失效")

        account = None
        if lease.owner_type and lease.owner_id is not None:
            account = await QuotaAccount.get_or_none(
                owner_type=lease.owner_type, owner_id=lease.owner_id
            )
        if account is not None and (account.status or "active") != "active":
            await cls._mark_invalid(lease, "owner_account_disabled")
            await cls._audit_renew_failed(
                lease, reason="owner_account_disabled", status_code=403
            )
            raise HTTPException(status_code=403, detail="配额账户已停用，租约失效")

        try:
            snapshot = await GatewayBudgetService.snapshot(lease)
        except Exception as exc:
            from services.gateway.gateway.logging import gateway_logger

            gateway_logger.error(
                f"[gateway] 续期额度校验失败 lease={lease.lease_id}: {type(exc).__name__}"
            )
            raise HTTPException(status_code=503, detail="续期额度校验暂不可用") from exc
        if snapshot.get("exhausted"):
            await cls._mark_invalid(lease, "quota_exhausted")
            await cls._audit_renew_failed(
                lease, reason="quota_exhausted", status_code=402
            )
            raise HTTPException(status_code=402, detail="额度已耗尽，租约失效")

        ttl = _ttl_seconds(
            ttl_seconds,
            "renew_ttl_seconds",
            owner_type=lease.owner_type,
            owner_id=lease.owner_id,
        )
        meta = dict(lease.meta or {})
        meta["ttl_seconds"] = ttl
        lease.meta = meta
        lease.expires_at = _now() + timedelta(seconds=ttl)
        await lease.save(update_fields=["expires_at", "meta", "updated_at"])
        # 续期后主动失效缓存，下一次数据面请求读到新过期时间
        await invalidate_lease_cache(lease.lease_id)
        return {
            "lease_id": lease.lease_id,
            "status": lease.status,
            "expires_at": _iso_utc(lease.expires_at),
            "ttl_seconds": ttl,
            "renew_after_seconds": int(ttl * 0.8),
        }

    @classmethod
    async def revoke(cls, lease_id: str, client_id: str) -> Dict[str, Any]:
        lease = await HarnessGatewayLease.get_or_none(lease_id=lease_id)
        if lease is None or lease.client_id != client_id:
            raise HTTPException(status_code=404, detail="租约不存在或不属于该客户端")
        return await cls.revoke_internal(
            lease_id,
            reason="client_request",
            actor_type="client",
            actor_id=client_id,
        )

    @classmethod
    async def revoke_internal(
        cls,
        lease_id: str,
        *,
        reason: str,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        event_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """吊销单个租约并写审计；幂等，且只影响目标 lease，不波及同租户其他租约。"""
        from services.gateway.gateway.lease_revoke import revoke_lease_internal

        return await revoke_lease_internal(
            lease_id,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            event_source=event_source,
        )

    @classmethod
    async def list_leases(cls, client_id: str, active_only: bool = True) -> list:
        query = HarnessGatewayLease.filter(client_id=client_id)
        if active_only:
            query = query.filter(status="active")
        leases = await query.order_by("-id").limit(100)
        return [
            {
                "lease_id": item.lease_id,
                "status": item.status,
                "session_no": item.session_no,
                "run_no": item.run_no,
                "expires_at": _iso_utc(item.expires_at),
                "key_fingerprint": item.key_fingerprint,
                "rpm_limit": item.rpm_limit,
                "request_count": item.request_count,
            }
            for item in leases
        ]

    # ---------------- 数据面鉴权 ----------------
    @classmethod
    async def authenticate(cls, token: str):
        """校验逻辑已下沉到 services.gateway.gateway.lease_auth（不依赖插件服务）。

        本方法保留为控制面/兼容入口，行为与历史实现完全一致。
        """
        return await validate_gateway_lease(token)
