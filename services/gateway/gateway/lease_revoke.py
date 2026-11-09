"""租约吊销（共享实现，P3 D-P3-4=A）。

L2 `GatewayLeaseService.revoke_internal` 与网关预算自动吊销共用同一份语义：
- 幂等：仅 active → revoked；
- 写穿租约短缓存（下一次请求立即读到 revoked）；
- 写审计 `gateway.lease_revoked`（高风险/拒绝）。
"""
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException

from packages.agentpanel_common.models.harness import HarnessGatewayLease
from .audit import record_gateway_quota_event
from packages.agentpanel_common.gateway_constants import GATEWAY_EVENT_SOURCE
from .lease_auth import invalidate_lease_cache


async def revoke_lease_internal(
    lease_id: str,
    *,
    reason: str,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    event_source: Optional[str] = None,
) -> Dict[str, Any]:
    """吊销单个租约并写审计；幂等，且只影响目标 lease，不波及同租户其他租约。"""
    lease = await HarnessGatewayLease.get_or_none(lease_id=lease_id)
    if lease is None:
        raise HTTPException(status_code=404, detail="租约不存在")
    changed = False
    if lease.status == "active":
        lease.status = "revoked"
        lease.revoked_at = datetime.now()
        await lease.save(update_fields=["status", "revoked_at", "updated_at"])
        changed = True
    # 吊销写穿缓存：下一次数据面请求立即读到 revoked，不等缓存 TTL
    await invalidate_lease_cache(lease_id)
    await record_gateway_quota_event(
        action="gateway.lease_revoked",
        lease_id=lease_id,
        reason=reason,
        detail={
            "changed": changed,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "event_source": event_source or GATEWAY_EVENT_SOURCE,
        },
        risk_level="high",
        decision="deny",
        client_id=lease.client_id,
        session_no=lease.session_no,
        run_no=lease.run_no,
        actor_type=actor_type,
        actor_id=actor_id or "gateway-budget",
    )
    return {"lease_id": lease.lease_id, "status": lease.status, "changed": changed}
