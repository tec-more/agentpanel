"""L3 额度后端：通过 L2 内部额度 API 预占/结算/释放（服务凭据 + 幂等键）。

入口在 lifespan 内调用 `configure_l3()` 注册到共享分派器。
"""
from typing import Any, Dict, List, Optional

from packages.agentpanel_common.domain import quota_backend as _shared
from packages.agentpanel_common.domain.quota_backend import QuotaUnavailable

from app import l2_quota_client


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
    owner_type, owner_id = _shared._owner_pair(owner)
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


async def settle(
    hold_id: str, usage_items: List[Dict[str, Any]], owner: Any = None
) -> Dict[str, Any]:
    owner_type, owner_id = _shared._owner_pair(owner) if owner is not None else (None, None)
    return await l2_quota_client.settle(
        hold_id, usage_items, owner_type=owner_type, owner_id=owner_id
    )


async def release(hold_id: str, reason: str = "") -> bool:
    if not hold_id:
        return False
    return await l2_quota_client.release(hold_id, reason=reason)


def configure_l3() -> None:
    """显式注册 L3 实现（lifespan 启动时调用）。"""
    _shared.configure(name="l3", reserve=reserve, settle=settle, release=release)


__all__ = ["QuotaUnavailable", "configure_l3", "reserve", "settle", "release"]
