"""额度执行后端分派。

- L2 进程：直接调用 QuotaService（既有语义不变）；
- L3 编排进程：只能调用 L2 内部额度 API（服务凭据 + 幂等键）；
  不可用时抛 QuotaUnavailable，由路由层转 503 fail-closed。
"""
from typing import Any, Dict, List, Optional

from base.common.quota.errors import QuotaError, QuotaReservationConflict
from base.common.quota.services.quota_service import QuotaService
from base.plugins.harness.services import l2_quota_client
from base.plugins.harness.services.l2_quota_client import QuotaUnavailable
from base.plugins.harness.services.orchestration_runtime import is_l3


async def reserve(
    owner: Any,
    items: Dict[str, float],
    *,
    hold_id: str,
    source: str,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    member_id: Optional[int] = None,
) -> str:
    if is_l3():
        owner_type, owner_id = _owner_pair(owner)
        return await l2_quota_client.reserve(
            owner_type=owner_type,
            owner_id=owner_id,
            items=items,
            hold_id=hold_id,
            source=source,
            ref_type=ref_type,
            ref_id=ref_id,
            member_id=member_id,
        )
    return await QuotaService.quota_estimate(
        owner, items, hold_id=hold_id, source=source,
        ref_type=ref_type, ref_id=ref_id, member_id=member_id,
    )


async def settle(hold_id: str, usage_items: List[Dict[str, Any]], owner: Any = None) -> Dict[str, Any]:
    if is_l3():
        owner_type, owner_id = _owner_pair(owner) if owner is not None else (None, None)
        return await l2_quota_client.settle(
            hold_id, usage_items, owner_type=owner_type, owner_id=owner_id
        )
    return await QuotaService.quota_settle(hold_id, usage_items, owner=owner)


async def release(hold_id: str, reason: str = "") -> bool:
    if not hold_id:
        return False
    if is_l3():
        return await l2_quota_client.release(hold_id, reason=reason)
    return await QuotaService.quota_release(hold_id)


def _owner_pair(owner: Any) -> tuple:
    if isinstance(owner, dict):
        return str(owner["owner_type"]), int(owner["owner_id"])
    if isinstance(owner, (tuple, list)) and len(owner) == 2:
        return str(owner[0]), int(owner[1])
    return str(owner.owner_type), int(owner.owner_id)


__all__ = ["QuotaUnavailable", "QuotaError", "QuotaReservationConflict", "reserve", "settle", "release"]
