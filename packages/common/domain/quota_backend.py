"""额度执行后端分派（入口显式注入实现，无角色探测）。

- app：启动时注入直调 `QuotaService` 的实现；
- 独立服务：启动时注入调用 app 内部额度 API 的实现（服务凭据 + 幂等键）。

未注入即视为额度后端不可用，抛 `QuotaUnavailable`，由路由层转 503 fail-closed。
"""
from typing import Any, Awaitable, Callable, Dict, List, Optional

from packages.common.domain.quota_errors import (
    QuotaError,
    QuotaReservationConflict,
)


class QuotaUnavailable(RuntimeError):
    """额度后端不可用（未初始化/超时/连接失败/5xx）；上层必须 fail-closed。"""


_reserve: Optional[Callable[..., Awaitable[str]]] = None
_settle: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None
_release: Optional[Callable[..., Awaitable[bool]]] = None
_backend_name = ""


def configure(
    *,
    name: str,
    reserve: Callable[..., Awaitable[str]],
    settle: Callable[..., Awaitable[Dict[str, Any]]],
    release: Callable[..., Awaitable[bool]],
) -> None:
    """由入口在启动生命周期内显式调用（禁止 import 副作用）。"""
    global _reserve, _settle, _release, _backend_name
    _reserve = reserve
    _settle = settle
    _release = release
    _backend_name = name


def configured() -> bool:
    return _reserve is not None and _settle is not None and _release is not None


def backend_name() -> str:
    return _backend_name


def _require() -> None:
    if not configured():
        raise QuotaUnavailable("额度后端未初始化（入口需在启动时调用 quota_backend.configure）")


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
    _require()
    return await _reserve(
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
    _require()
    return await _settle(hold_id, usage_items, owner)


async def release(hold_id: str, reason: str = "") -> bool:
    if not hold_id:
        return False
    _require()
    return await _release(hold_id, reason)


def _owner_pair(owner: Any) -> tuple:
    if isinstance(owner, dict):
        return str(owner["owner_type"]), int(owner["owner_id"])
    if isinstance(owner, (tuple, list)) and len(owner) == 2:
        return str(owner[0]), int(owner[1])
    return str(owner.owner_type), int(owner.owner_id)


__all__ = [
    "QuotaError",
    "QuotaReservationConflict",
    "QuotaUnavailable",
    "backend_name",
    "configure",
    "configured",
    "release",
    "reserve",
    "settle",
]
