"""
Harness 客户端凭据服务

安全约定：
- secret 明文只在签发响应中回显一次，DB 只存 SHA-256；
- 校验使用 hmac.compare_digest，避免时序侧信道；
- 凭据支持 X-Harness-Client-Id/X-Harness-Secret 头，或 Authorization: Bearer <client_id>.<secret>。
"""
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException, Request, status

from base.plugins.harness.models.harness import HarnessClient

SECRET_PREFIX = "hsc_"


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class HarnessClientService:
    @classmethod
    async def issue(
        cls,
        name: str,
        scopes: Optional[List[str]] = None,
        allowed_ips: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        created_by: Optional[int] = None,
        description: Optional[str] = None,
    ) -> Tuple[HarnessClient, str]:
        """签发客户端凭据，返回 (client, 明文 secret)。"""
        client_id = f"hcli_{secrets.token_hex(8)}"
        secret = SECRET_PREFIX + secrets.token_urlsafe(32)
        client = await HarnessClient.create(
            client_id=client_id,
            name=name,
            secret_hash=hash_secret(secret),
            secret_prefix=secret[:12],
            status="active",
            scopes=scopes or [],
            allowed_ips=allowed_ips,
            expires_at=expires_at,
            created_by=created_by,
            description=description,
        )
        return client, secret

    @classmethod
    async def verify(cls, client_id: str, secret: str) -> Optional[HarnessClient]:
        client = await HarnessClient.get_or_none(client_id=client_id)
        if client is None:
            return None
        if client.status != "active":
            return None
        if client.expires_at is not None:
            expires = client.expires_at.replace(tzinfo=None)
            if expires <= datetime.now():
                return None
        if not hmac.compare_digest(client.secret_hash, hash_secret(secret or "")):
            return None
        return client

    @classmethod
    async def verify_bearer(cls, token: str) -> Optional[HarnessClient]:
        """Bearer <client_id>.<secret>"""
        if not token or "." not in token:
            return None
        client_id, secret = token.split(".", 1)
        return await cls.verify(client_id, secret)

    @classmethod
    async def touch(cls, client: HarnessClient) -> None:
        try:
            await HarnessClient.filter(id=client.id).update(last_used_at=datetime.now())
        except Exception:
            pass

    @classmethod
    async def revoke(cls, client_id: str) -> bool:
        client = await HarnessClient.get_or_none(client_id=client_id)
        if client is None:
            return False
        client.status = "revoked"
        client.revoked_at = datetime.now()
        await client.save()
        return True


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


async def require_harness_client(request: Request) -> HarnessClient:
    """FastAPI 依赖：校验 Harness 客户端凭据。"""
    client_id = request.headers.get("X-Harness-Client-Id")
    secret = request.headers.get("X-Harness-Secret")
    if client_id and secret:
        client = await HarnessClientService.verify(client_id, secret)
    else:
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        client = await HarnessClientService.verify_bearer(token) if token else None

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Harness 客户端凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    allowed_ips = client.allowed_ips or []
    if allowed_ips and _client_ip(request) not in allowed_ips:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="来源 IP 不在白名单")

    await HarnessClientService.touch(client)
    request.state.harness_client = client
    request.state.harness_client_id = client.client_id
    return client
