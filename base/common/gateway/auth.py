"""网关数据面独立鉴权：只接受租约虚拟 key，不接受 JWT / 登录态凭据。"""
from fastapi import HTTPException, Request

from base.common.gateway.audit import record_gateway_auth_reject
from base.common.gateway.constants import (
    GATEWAY_VIRTUAL_KEY_PREFIX,
    is_gateway_virtual_key,
    looks_like_jwt,
)
from base.common.gateway.lease_auth import authenticate as validate_gateway_lease
from base.common.gateway.logging import gateway_logger


def _bearer_token(request: Request) -> str:
    raw = request.headers.get("authorization") or ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return (request.headers.get("x-api-key") or "").strip()


def _token_kind(token: str) -> str:
    if is_gateway_virtual_key(token):
        return "virtual_key"
    if looks_like_jwt(token):
        return "jwt"
    return "unknown"


async def require_gateway_lease(request: Request):
    """FastAPI 依赖：网关专属鉴权链（与业务 get_current_user_id 完全独立）。

    - 缺凭据 / JWT / 非 dgw.* 格式一律拒绝；
    - 通过后把租约放入 request.state，供数据面记账使用。
    """
    token = _bearer_token(request)
    kind = _token_kind(token)

    if not token:
        await record_gateway_auth_reject(request, reason="missing_credential", token_kind="none")
        raise HTTPException(status_code=401, detail="缺少网关租约虚拟 key")

    if kind == "jwt":
        gateway_logger.warning(f"[gateway] 拒绝 JWT 凭据 path={request.url.path}")
        await record_gateway_auth_reject(request, reason="jwt_not_allowed", token_kind="jwt")
        raise HTTPException(status_code=401, detail="网关只接受租约虚拟 key，不接受 JWT/登录态凭据")

    if not is_gateway_virtual_key(token):
        await record_gateway_auth_reject(request, reason="invalid_key_format", token_kind=kind)
        raise HTTPException(status_code=401, detail="网关只接受租约虚拟 key")

    try:
        lease = await validate_gateway_lease(token)
    except HTTPException as exc:
        gateway_logger.warning(
            f"[gateway] 租约校验失败 status={exc.status_code} path={request.url.path}"
        )
        await record_gateway_auth_reject(
            request,
            reason=f"lease_rejected:{exc.status_code}",
            token_kind="virtual_key",
            status_code=int(exc.status_code),
        )
        raise

    request.state.gateway_lease = lease
    request.state.gateway_key_kind = "virtual_key"
    if lease.client_id:
        request.state.gateway_client_id = lease.client_id
    return lease


__all__ = ["require_gateway_lease", "GATEWAY_VIRTUAL_KEY_PREFIX"]
