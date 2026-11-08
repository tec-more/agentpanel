"""L3 编排内部认证：只接受服务凭据，不接受用户 JWT / 网关租约 key / 匿名。

签名约定：
    secret_hash = SHA-256(明文密钥) 小写十六进制（库中只存该值）
    signature   = HMAC-SHA256(key=secret_hash,
                              msg=timestamp + "\\n" + METHOD + "\\n" + path + "\\n" + sha256(body))
    headers     = X-Service-Id / X-Service-Timestamp / X-Service-Signature
"""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request

from packages.agentpanel_common.gateway.constants import is_gateway_virtual_key, looks_like_jwt
from packages.agentpanel_common.security import build_signature, signature_payload
from base.plugins.harness.services.orchestration_config import (
    auth_timestamp_window_seconds,
    internal_allowed_ips,
    orchestration_config,
    write_enabled,
)
from base.plugins.harness.services.readonly_db import get_readonly_db

ORCHESTRATION_EVENT_SOURCE = "orchestration"

# 稳定错误码（写入响应 data.error_code）
ERROR_MISSING = "service_auth_missing_credential"
ERROR_JWT = "service_auth_jwt_rejected"
ERROR_LEASE_KEY = "service_auth_lease_key_rejected"
ERROR_INVALID = "service_auth_invalid_credential"
ERROR_TIMESTAMP = "service_auth_timestamp_skew"
ERROR_IP = "service_auth_ip_not_allowed"
ERROR_SCOPE = "service_auth_scope_denied"
ERROR_WRITE_DISABLED = "orchestration_write_disabled"
ERROR_NOT_PRIMARY = "orchestration_not_primary"
ERROR_DEPENDENCY = "orchestration_dependency_unavailable"


class ServiceAuthError(RuntimeError):
    def __init__(self, error_code: str, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code

    def to_dict(self) -> Dict[str, Any]:
        return {"error_code": self.error_code, "message": self.message}


def _bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("x-api-key") or "").strip()


def _rejected_token_kind(request: Request) -> Optional[str]:
    """识别不允许的凭据类型；按严重度优先返回 jwt / lease_key / unknown。"""
    token = _bearer_token(request)
    if not token:
        return None
    if looks_like_jwt(token):
        return "jwt"
    if is_gateway_virtual_key(token):
        return "lease_key"
    return "unknown"


def _signature_payload(timestamp: str, method: str, path: str, body: bytes) -> str:
    """兼容保留：实现位于共享包 `agentpanel_common.security`。"""
    return signature_payload(timestamp, method, path, body)


def _parse_scopes(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return [item.strip() for item in raw.split(",") if item.strip()]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def _normalize_ip(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("::ffff:"):
        return text[7:]
    return text


def _client_ip(request: Request) -> str:
    return _normalize_ip(request.client.host if request.client else "")


def _timestamp_ok(request: Request) -> Tuple[bool, str]:
    raw = (request.headers.get("x-service-timestamp") or "").strip()
    try:
        ts = int(raw)
    except (TypeError, ValueError):
        return False, raw
    window = auth_timestamp_window_seconds()
    return abs(int(time.time()) - ts) <= window, raw


async def _write_reject_audit(request: Request, error: ServiceAuthError, token_kind: str) -> None:
    """拒绝事件留痕；审计失败不得影响拒绝响应。"""
    try:
        from base.plugins.harness.services.audit_service import HarnessAuditService

        await asyncio.wait_for(
            HarnessAuditService.record(
                "internal.auth_rejected",
                actor_type="service",
                actor_id=(request.headers.get("x-service-id") or None),
                target_type="orchestration_endpoint",
                target_id=str(request.url.path)[:128],
                risk_level="medium",
                decision="deny",
                event_source=ORCHESTRATION_EVENT_SOURCE,
                detail={
                    "error_code": error.error_code,
                    "message": error.message,
                    "status": error.status_code,
                    "token_kind": token_kind,
                    "method": request.method,
                },
                request=request,
            ),
            timeout=2,
        )
    except Exception:
        pass


async def _load_credential(service_id: str) -> Optional[Dict[str, Any]]:
    try:
        row = await get_readonly_db().fetchrow(
            "SELECT service_id, secret_hash, scopes, status, expires_at "
            "FROM service_credential WHERE service_id = $1",
            service_id,
        )
    except Exception as exc:
        raise ServiceAuthError(
            ERROR_DEPENDENCY,
            f"凭据校验依赖不可用: {type(exc).__name__}: {exc}",
            status_code=503,
        )
    if row is None:
        return None
    return {
        "service_id": row["service_id"],
        "secret_hash": row["secret_hash"],
        "scopes": _parse_scopes(row["scopes"]),
        "status": row["status"],
        "expires_at": row["expires_at"],
    }


async def authenticate(request: Request, required_scopes: Tuple[str, ...] = ()) -> Dict[str, Any]:
    token_kind = _rejected_token_kind(request)
    service_id = (request.headers.get("x-service-id") or "").strip()

    if token_kind == "jwt":
        error = ServiceAuthError(ERROR_JWT, "编排内部接口不接受用户 JWT，只接受服务凭据", 401)
        await _write_reject_audit(request, error, "jwt")
        raise error
    if token_kind == "lease_key":
        error = ServiceAuthError(ERROR_LEASE_KEY, "编排内部接口不接受网关租约 key", 401)
        await _write_reject_audit(request, error, "lease_key")
        raise error
    if token_kind == "unknown":
        error = ServiceAuthError(ERROR_INVALID, "无法识别的凭据类型", 401)
        await _write_reject_audit(request, error, "unknown")
        raise error
    if not service_id:
        error = ServiceAuthError(ERROR_MISSING, "缺少服务凭据", 401)
        await _write_reject_audit(request, error, "anonymous")
        raise error

    timestamp_ok, raw_ts = _timestamp_ok(request)
    if not timestamp_ok:
        error = ServiceAuthError(ERROR_TIMESTAMP, f"服务凭据时间戳缺失或超出时间窗: {raw_ts}", 401)
        await _write_reject_audit(request, error, "service")
        raise error

    credential = await _load_credential(service_id)
    if credential is None or credential.get("status") != "active":
        error = ServiceAuthError(ERROR_INVALID, "服务凭据无效、已禁用或已吊销", 401)
        await _write_reject_audit(request, error, "service")
        raise error

    expires_at = credential.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, datetime):
            if expires_at.tzinfo is None:
                expired = expires_at < datetime.now()
            else:
                expired = expires_at < datetime.now(timezone.utc)
            if expired:
                error = ServiceAuthError(ERROR_INVALID, "服务凭据已过期", 401)
                await _write_reject_audit(request, error, "service")
                raise error

    provided = (request.headers.get("x-service-signature") or "").strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    body = await request.body()
    expected = build_signature(
        credential["secret_hash"], raw_ts, request.method, request.url.path, body
    )
    if not provided or not hmac.compare_digest(expected, provided.lower()):
        error = ServiceAuthError(ERROR_INVALID, "服务凭据签名校验失败", 401)
        await _write_reject_audit(request, error, "service")
        raise error

    allowed_ips = internal_allowed_ips()
    client_ip = _client_ip(request)
    if allowed_ips and client_ip not in allowed_ips:
        error = ServiceAuthError(ERROR_IP, f"来源 IP 不允许访问内部接口: {client_ip}", 403)
        await _write_reject_audit(request, error, "service")
        raise error

    scopes = credential.get("scopes") or []
    if required_scopes and "*" not in scopes:
        missing = [scope for scope in required_scopes if scope not in scopes]
        if missing:
            error = ServiceAuthError(ERROR_SCOPE, f"服务凭据缺少 scope: {', '.join(missing)}", 403)
            await _write_reject_audit(request, error, "service")
            raise error

    request.state.service_id = credential["service_id"]
    request.state.service_scopes = scopes
    return {
        "service_id": credential["service_id"],
        "scopes": scopes,
        "auth_kind": "service",
    }


def require_service_credential(*required_scopes: str):
    async def dependency(request: Request) -> Dict[str, Any]:
        return await authenticate(request, tuple(required_scopes))

    return dependency


def ensure_write_enabled() -> None:
    """写接口总开关；P1.2 起的写路由统一依赖它。

    第二道闸：只有 mode=proxy_l3 的进程才是写主。mode=l2 时 L3 进程必须拒绝写，
    避免同一 run 被 L2/L3 两边同时推进。
    """
    if not write_enabled():
        raise ServiceAuthError(
            ERROR_WRITE_DISABLED,
            "编排服务写接口未启用（orchestration.write_enabled=false）",
            status_code=409,
        )
    if orchestration_config().get("mode") != "proxy_l3":
        raise ServiceAuthError(
            ERROR_NOT_PRIMARY,
            "编排服务不是当前写主（orchestration.mode != proxy_l3）",
            status_code=409,
        )
