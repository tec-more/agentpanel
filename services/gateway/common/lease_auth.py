"""网关租约校验（common 层，零插件服务依赖）

校验链：虚拟 key 格式 → 租约存在 → 状态 active → 未过期 → SHA-256 常量时间比对
→ 租约 RPM → 绑定会话 open → 绑定 run 未终态。

约束：
- 只读取 `harness_gateway_lease` / `harness_session` / `harness_run` 三张表；
- 不导入 `base.plugins.harness` 的任何服务或模型，harness 插件未加载时网关仍可启动；
- harness 侧保留签发、续期、吊销与业务语义，仅复用本模块的校验能力。
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from tortoise import Tortoise

from .runtime import gateway_config, lease_cache_ttl_seconds
from .logging import gateway_logger

VIRTUAL_KEY_PREFIX = "dgw"
TERMINAL_RUN_STATUSES = {
    "succeeded", "failed", "cancelled", "timeout", "completed", "closed",
}

# 租约鉴权状态短缓存。只缓存非敏感快照；吊销/失效/续期时写穿删除。
LEASE_CACHE_PREFIX = "gw:lease:state:"

# 数据面专用限流窗口（按 lease_id 计数），与业务接口限流完全分离。
_rate_windows: Dict[str, Dict[str, float]] = {}


def _inc_lease_cache(result: str) -> None:
    """T7.4 观测旁路：任何异常都不得影响租约鉴权链路。"""
    try:
        from packages.common.l3_metrics import inc_lease_cache

        inc_lease_cache(result)
    except Exception:
        pass


@dataclass
class GatewayLease:
    """鉴权通过后的租约快照（替代插件层 ORM 模型，供数据面只读使用）"""

    lease_id: str
    client_id: str
    key_hash: str
    status: str
    expires_at: Optional[datetime]
    rpm_limit: int = 60
    key_prefix: Optional[str] = None
    key_fingerprint: Optional[str] = None
    session_no: Optional[str] = None
    run_no: Optional[str] = None
    owner_type: Optional[str] = None
    owner_id: Optional[int] = None
    member_id: Optional[int] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    request_count: int = 0
    meta: Dict[str, Any] = field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_virtual_key(token: str) -> Optional[str]:
    """从 dgw.<lease_id>.<secret> 中取出 lease_id（不做鉴权）。"""
    parts = (token or "").strip().split(".")
    if len(parts) != 3 or parts[0] != VIRTUAL_KEY_PREFIX or not parts[1] or not parts[2]:
        return None
    return parts[1]


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _rate_limit_ok(lease_id: str, limit: int) -> bool:
    now = time.time()
    window = _rate_windows.get(lease_id)
    if window is None or now - window["start"] >= 60:
        _rate_windows[lease_id] = {"start": now, "count": 1.0}
        return True
    if window["count"] >= limit:
        return False
    window["count"] += 1.0
    return True


def _connection():
    return Tortoise.get_connection("postgres")


async def _fetch_lease(lease_id: str) -> Optional[Dict[str, Any]]:
    sql = """
        SELECT lease_id, key_hash, key_prefix, key_fingerprint, client_id,
               session_no, run_no, owner_type, owner_id, member_id,
               provider, model, status, expires_at, last_used_at, revoked_at,
               request_count, rpm_limit, meta
        FROM harness_gateway_lease
        WHERE lease_id = $1
        LIMIT 1
    """
    rows = await _connection().execute_query_dict(sql, [lease_id])
    return rows[0] if rows else None


def _iso_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def _cache() -> Any:
    """获取 Redis 缓存；不可用返回 None（调用方回落 DB）。"""
    try:
        from packages.common.cache import RedisCache

        cache = await RedisCache.get_instance()
        return cache if cache.is_enabled() else None
    except Exception:
        return None


def _lease_to_payload(lease: GatewayLease) -> Dict[str, Any]:
    return {
        "lease_id": lease.lease_id,
        "client_id": lease.client_id,
        "key_hash": lease.key_hash,
        "key_prefix": lease.key_prefix,
        "key_fingerprint": lease.key_fingerprint,
        "status": lease.status,
        "expires_at": _iso_utc(lease.expires_at),
        "rpm_limit": lease.rpm_limit,
        "session_no": lease.session_no,
        "run_no": lease.run_no,
        "owner_type": lease.owner_type,
        "owner_id": lease.owner_id,
        "member_id": lease.member_id,
        "provider": lease.provider,
        "model": lease.model,
        "last_used_at": _iso_utc(lease.last_used_at),
        "revoked_at": _iso_utc(lease.revoked_at),
        "request_count": lease.request_count,
        "meta": lease.meta or {},
    }


def _payload_to_lease(payload: Dict[str, Any]) -> Optional[GatewayLease]:
    if not isinstance(payload, dict) or not payload.get("lease_id"):
        return None
    return GatewayLease(
        lease_id=payload["lease_id"],
        client_id=payload.get("client_id") or "",
        key_hash=payload.get("key_hash") or "",
        status=payload.get("status") or "",
        expires_at=_parse_dt(payload.get("expires_at")),
        rpm_limit=int(payload.get("rpm_limit") or 60),
        key_prefix=payload.get("key_prefix"),
        key_fingerprint=payload.get("key_fingerprint"),
        session_no=payload.get("session_no"),
        run_no=payload.get("run_no"),
        owner_type=payload.get("owner_type"),
        owner_id=payload.get("owner_id"),
        member_id=payload.get("member_id"),
        provider=payload.get("provider"),
        model=payload.get("model"),
        last_used_at=_parse_dt(payload.get("last_used_at")),
        revoked_at=_parse_dt(payload.get("revoked_at")),
        request_count=int(payload.get("request_count") or 0),
        meta=payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
    )


async def _get_cached_lease(lease_id: str) -> Optional[GatewayLease]:
    cache = await _cache()
    if cache is None:
        _inc_lease_cache("unavailable")
        return None
    try:
        payload = await cache.get(f"{LEASE_CACHE_PREFIX}{lease_id}")
        lease = _payload_to_lease(payload) if payload else None
        # hit=命中；payload 无效或为空均需回源 DB，统一记 miss
        _inc_lease_cache("hit" if lease is not None else "miss")
        return lease
    except Exception:
        _inc_lease_cache("error")
        return None


async def _set_cached_lease(lease: GatewayLease) -> None:
    cache = await _cache()
    if cache is None:
        return
    try:
        ttl = lease_cache_ttl_seconds(gateway_config())
        await cache.set(
            f"{LEASE_CACHE_PREFIX}{lease.lease_id}", _lease_to_payload(lease), expire=ttl
        )
    except Exception:
        pass


async def invalidate_lease_cache(lease_id: str) -> None:
    """吊销/续期/失效时写穿删除；失败由短 TTL 兜底，不阻断业务。"""
    cache = await _cache()
    if cache is None:
        return
    try:
        await cache.delete(f"{LEASE_CACHE_PREFIX}{lease_id}")
    except Exception:
        pass


async def _fetch_session_status(session_no: str) -> Optional[str]:
    rows = await _connection().execute_query_dict(
        "SELECT status FROM harness_session WHERE session_no = $1 LIMIT 1", [session_no]
    )
    return rows[0].get("status") if rows else None


async def _fetch_run_status(run_no: str) -> Optional[str]:
    rows = await _connection().execute_query_dict(
        "SELECT status FROM harness_run WHERE run_no = $1 LIMIT 1", [run_no]
    )
    return rows[0].get("status") if rows else None


async def _touch_lease(lease_id: str) -> None:
    """使用统计失败不阻断数据面流量。"""
    try:
        await _connection().execute_query(
            "UPDATE harness_gateway_lease "
            "SET last_used_at = NOW(), request_count = COALESCE(request_count, 0) + 1 "
            "WHERE lease_id = $1",
            [lease_id],
        )
    except Exception as exc:
        gateway_logger.warning(f"[gateway] 租约使用统计更新失败: {type(exc).__name__}")


def _row_to_lease(row: Dict[str, Any]) -> GatewayLease:
    meta = row.get("meta")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return GatewayLease(
        lease_id=row["lease_id"],
        client_id=row.get("client_id") or "",
        key_hash=row.get("key_hash") or "",
        status=row.get("status") or "",
        expires_at=row.get("expires_at"),
        rpm_limit=int(row.get("rpm_limit") or 60),
        key_prefix=row.get("key_prefix"),
        key_fingerprint=row.get("key_fingerprint"),
        session_no=row.get("session_no"),
        run_no=row.get("run_no"),
        owner_type=row.get("owner_type"),
        owner_id=row.get("owner_id"),
        member_id=row.get("member_id"),
        provider=row.get("provider"),
        model=row.get("model"),
        last_used_at=row.get("last_used_at"),
        revoked_at=row.get("revoked_at"),
        request_count=int(row.get("request_count") or 0),
        meta=meta,
    )


async def authenticate(token: str) -> GatewayLease:
    """校验租约虚拟 key；失败抛 401/403/429，语义与插件层历史实现一致。

    租约状态优先读 Redis 短缓存（5-10s），未命中回填；缓存不可用回落 DB。
    """
    lease_id = parse_virtual_key(token)
    if not lease_id:
        raise HTTPException(status_code=401, detail="网关虚拟 key 格式非法")

    lease = await _get_cached_lease(lease_id)
    if lease is None:
        try:
            row = await _fetch_lease(lease_id)
        except Exception as exc:
            gateway_logger.error(f"[gateway] 租约查询失败 lease_id={lease_id}: {type(exc).__name__}")
            raise HTTPException(status_code=503, detail="网关鉴权暂不可用") from exc

        if row is None:
            raise HTTPException(status_code=401, detail="网关虚拟 key 无效")

        lease = _row_to_lease(row)
        await _set_cached_lease(lease)

    if lease.status == "invalid":
        raise HTTPException(status_code=401, detail="网关租约已失效")
    if lease.status != "active":
        raise HTTPException(status_code=401, detail="网关租约已吊销")

    expires = _aware(lease.expires_at)
    if expires is not None and expires <= _now():
        raise HTTPException(status_code=401, detail="网关租约已过期")

    provided_hash = hash_secret(token.split(".", 2)[2])
    if not hmac.compare_digest(lease.key_hash or "", provided_hash):
        raise HTTPException(status_code=401, detail="网关虚拟 key 无效")

    if not _rate_limit_ok(lease.lease_id, int(lease.rpm_limit or 60)):
        raise HTTPException(status_code=429, detail="网关租约请求频率超限")

    if lease.session_no:
        try:
            session_status = await _fetch_session_status(lease.session_no)
        except Exception as exc:
            gateway_logger.error(f"[gateway] 会话校验失败 session={lease.session_no}: {type(exc).__name__}")
            raise HTTPException(status_code=503, detail="网关鉴权暂不可用") from exc
        if session_status != "open":
            raise HTTPException(status_code=403, detail="会话已关闭，租约不可用")

    if lease.run_no:
        try:
            run_status = await _fetch_run_status(lease.run_no)
        except Exception as exc:
            gateway_logger.error(f"[gateway] 运行校验失败 run={lease.run_no}: {type(exc).__name__}")
            raise HTTPException(status_code=503, detail="网关鉴权暂不可用") from exc
        if run_status is None:
            raise HTTPException(status_code=403, detail="绑定运行不存在")
        if run_status in TERMINAL_RUN_STATUSES:
            raise HTTPException(status_code=403, detail="运行已结束，租约不可用")

    await _touch_lease(lease.lease_id)
    lease.request_count = int(lease.request_count) + 1
    lease.last_used_at = _now()
    return lease


def renew_hint(lease: GatewayLease) -> Dict[str, str]:
    """数据面响应头提示：剩余 <30% TTL 时返回 renew_after（剩余秒数）。

    仅作续期兜底提示，不参与请求中途校验。
    """
    meta = lease.meta or {}
    try:
        ttl = int(meta.get("ttl_seconds") or 0)
    except (TypeError, ValueError):
        ttl = 0
    expires = _aware(lease.expires_at)
    if ttl <= 0 or expires is None:
        return {}
    remaining = (expires - _now()).total_seconds()
    if remaining < 0:
        remaining = 0
    if remaining >= ttl * 0.30:
        return {}
    return {"renew_after": str(int(remaining))}


__all__ = [
    "VIRTUAL_KEY_PREFIX",
    "TERMINAL_RUN_STATUSES",
    "GatewayLease",
    "authenticate",
    "hash_secret",
    "parse_virtual_key",
    "renew_hint",
    "invalidate_lease_cache",
]
