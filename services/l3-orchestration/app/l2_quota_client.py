"""L3 编排 → L2 内部额度 API 客户端。

契约（与 spec §16.3 一致）：
- reserve/settle/release 走服务凭据（scope=quota:operate）；
- 幂等：reserve 由 hold_id 唯一约束、settle 由 usage_record.idem_key 唯一约束；
- 超时、连接失败、下游 5xx 一律抛 QuotaUnavailable，由上层转 503 fail-closed；
  不重试、不本地兜底扣减、不伪造成功。
"""
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from packages.agentpanel_common.domain.quota_errors import QuotaError, QuotaReservationConflict
from app.config import orchestration_config
from app.auth import build_signature

SCOPE = "quota:operate"


class QuotaUnavailable(RuntimeError):
    """L2 额度服务不可用（超时/连接失败/5xx）；上层必须 fail-closed。"""


def _credentials() -> tuple:
    cfg = orchestration_config()
    service_id = str(cfg.get("l2_service_id") or "").strip()
    secret_env = str(cfg.get("l2_service_secret_env") or "").strip()
    secret = os.getenv(secret_env, "").strip() if secret_env else ""
    return service_id, secret


def _base_url() -> str:
    return str(orchestration_config().get("l2_internal_base_url") or "").rstrip("/")


def _timeout() -> float:
    try:
        return max(0.5, float(orchestration_config().get("internal_timeout_seconds") or 5))
    except (TypeError, ValueError):
        return 5.0


async def _post_impl(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    base_url = _base_url()
    service_id, secret = _credentials()
    if not base_url or not service_id or not secret:
        raise QuotaUnavailable("L2 额度 API 服务凭据未配置（l2_service_id/环境变量）")

    path = f"/internal/v1/harness/quota/{action}"
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    key = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Service-Id": service_id,
        "X-Service-Timestamp": timestamp,
        "X-Service-Signature": build_signature(key, timestamp, "POST", path, body),
    }

    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            response = await client.post(base_url + path, headers=headers, content=body)
    except Exception as exc:
        raise QuotaUnavailable(f"L2 额度 {action} 调用失败: {type(exc).__name__}: {exc}") from exc

    try:
        raw = response.json()
    except Exception:
        raw = {}
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    if not isinstance(data, dict):
        data = {}

    if response.status_code == 200:
        return data
    if response.status_code == 429:
        raise QuotaError(
            item=str(data.get("item") or "token"),
            remaining=float(data.get("remaining") or 0),
            estimated=float(data.get("estimated") or 0),
            message=str(raw.get("msg") or data.get("message") or "额度不足"),
        )
    if response.status_code == 409:
        if str(data.get("error_code") or "") == "orchestration_not_primary":
            # 单写者闸：L2 不是额度主写者时，L3 一律 fail-closed，不伪装成预占冲突
            raise QuotaUnavailable("L2 额度主写者未启用（orchestration_not_primary）")
        raise QuotaReservationConflict(
            str(data.get("hold_id") or payload.get("hold_id") or ""),
            str(data.get("status") or "unknown"),
        )
    raise QuotaUnavailable(
        f"L2 额度 {action} 返回 {response.status_code}: {str(raw.get('msg') or raw)[:160]}"
    )


def _inc_quota_operation(action: str, result: str, reason: str = "") -> None:
    """T7.4 观测旁路：埋点失败不得影响额度调用。"""
    try:
        from packages.agentpanel_common.l3_metrics import inc_quota_operation

        inc_quota_operation(action, result, reason)
    except Exception:
        pass


async def _post(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """T7.4 观测包装：记录预占/结算/释放成败，异常类型与传播语义不变。"""
    try:
        data = await _post_impl(action, payload)
    except Exception as exc:
        _inc_quota_operation(action, "failed", type(exc).__name__)
        raise
    _inc_quota_operation(action, "ok")
    return data


async def reserve(
    *,
    owner_type: str,
    owner_id: int,
    items: Dict[str, float],
    hold_id: str,
    source: str,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    member_id: Optional[int] = None,
) -> str:
    data = await _post("reserve", {
        "owner_type": owner_type,
        "owner_id": int(owner_id),
        "items": {k: float(v) for k, v in (items or {}).items()},
        "hold_id": hold_id,
        "source": source,
        "ref_type": ref_type,
        "ref_id": ref_id,
        "member_id": member_id,
    })
    return str(data.get("hold_id") or hold_id)


async def settle(
    hold_id: str,
    usage_items: List[Dict[str, Any]],
    *,
    owner_type: Optional[str] = None,
    owner_id: Optional[int] = None,
) -> Dict[str, Any]:
    return await _post("settle", {
        "hold_id": hold_id,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "usage_items": usage_items,
    })


async def release(hold_id: str, reason: str = "") -> bool:
    data = await _post("release", {"hold_id": hold_id, "reason": reason})
    return bool(data.get("released", True))


__all__ = ["QuotaUnavailable", "reserve", "settle", "release", "SCOPE"]
