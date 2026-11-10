"""app 额度执行后端：直调 `QuotaService`，并在启动时注册到共享分派器。

P2 起 `quota_backend` 的共享实现不再做进程角色探测；app 入口通过
`configure_app()` 显式注入本文件的实现（由 harness `on_startup` 调用）。
"""
from typing import Any, Dict, List, Optional

from base.common.quota.errors import QuotaError, QuotaReservationConflict
from base.common.quota.services.quota_service import QuotaService
from packages.common.domain import quota_backend as _shared
from packages.common.domain.quota_backend import QuotaUnavailable


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
    return await QuotaService.quota_estimate(
        owner,
        items,
        hold_id=hold_id,
        source=source,
        ref_type=ref_type,
        ref_id=ref_id,
        member_id=member_id,
    )


async def settle(
    hold_id: str, usage_items: List[Dict[str, Any]], owner: Any = None
) -> Dict[str, Any]:
    return await QuotaService.quota_settle(hold_id, usage_items, owner=owner)


async def release(hold_id: str, reason: str = "") -> bool:
    if not hold_id:
        return False
    return await QuotaService.quota_release(hold_id)


def configure_app() -> None:
    """显式注册 app 实现（启动生命周期调用，禁止 import 副作用）。"""
    _shared.configure(name="app", reserve=reserve, settle=settle, release=release)


__all__ = [
    "QuotaUnavailable",
    "QuotaError",
    "QuotaReservationConflict",
    "configure_app",
    "reserve",
    "settle",
    "release",
]
