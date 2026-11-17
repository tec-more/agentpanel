"""ContentOps 对外 API Key 服务（M4）。

安全约定：
- secret 明文仅签发时回显一次，DB 只存 SHA-256；
- 校验走常量时间比对 hmac.compare_digest；
- 绑定 CUS 租户归属，外部调用继承该 owner 做归属过滤。
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from base.plugins.contentops.models import ContentopsApiKey

SECRET_PREFIX = "csk_"          # contentops secret key
KEY_ID_PREFIX = "ckey_"


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


# 对外只读 scope 全集（防止垃圾授权）
OPENAPI_SCOPES = ("compliance:check", "rules:read")


class ContentopsApiKeyService:
    @classmethod
    async def issue(
        cls,
        name: str,
        owner_id: int,
        scopes: Optional[List[str]] = None,
        owner_type: str = "cus",
        allowed_ips: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        rate_limit_rpm: int = 60,
        created_by: Optional[int] = None,
        description: Optional[str] = None,
    ) -> Tuple[ContentopsApiKey, str]:
        """签发 API Key，返回 (record, 明文 secret)。"""
        clean_scopes = [s for s in (scopes or []) if s in OPENAPI_SCOPES]
        if not clean_scopes:
            clean_scopes = list(OPENAPI_SCOPES)
        key_id = f"{KEY_ID_PREFIX}{secrets.token_hex(8)}"
        secret = SECRET_PREFIX + secrets.token_urlsafe(32)
        record = await ContentopsApiKey.create(
            key_id=key_id, name=name,
            secret_hash=hash_secret(secret), secret_prefix=secret[:12],
            status="active", scopes=clean_scopes,
            owner_type=owner_type, owner_id=owner_id,
            allowed_ips=allowed_ips, expires_at=expires_at,
            rate_limit_rpm=rate_limit_rpm, created_by=created_by,
            description=description,
        )
        return record, secret

    @classmethod
    async def verify(cls, key_id: str, secret: str) -> Optional[ContentopsApiKey]:
        record = await ContentopsApiKey.get_or_none(key_id=key_id)
        if record is None or record.status != "active":
            return None
        if record.expires_at is not None:
            expires = record.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= datetime.now(timezone.utc):
                return None
        if not hmac.compare_digest(record.secret_hash, hash_secret(secret or "")):
            return None
        return record

    @classmethod
    async def revoke(cls, key_id_value: str) -> bool:
        """按 key_id（公开标识）吊销。"""
        record = await ContentopsApiKey.get_or_none(key_id=key_id_value)
        if record is None:
            return False
        record.status = "revoked"
        record.revoked_at = datetime.now(timezone.utc)
        await record.save()
        return True

    @classmethod
    async def touch(cls, record: ContentopsApiKey) -> None:
        try:
            record.last_used_at = datetime.now(timezone.utc)
            await record.save(update_fields=["last_used_at", "updated_at"])
        except Exception:
            pass

    @classmethod
    def to_safe_dict(cls, record: ContentopsApiKey) -> dict:
        """对外展示：剔除 secret_hash。"""
        d = {
            "key_id": record.key_id, "name": record.name, "status": record.status,
            "secret_prefix": record.secret_prefix, "scopes": record.scopes,
            "owner_type": record.owner_type, "owner_id": record.owner_id,
            "allowed_ips": record.allowed_ips, "expires_at": record.expires_at,
            "rate_limit_rpm": record.rate_limit_rpm, "last_used_at": record.last_used_at,
            "created_at": record.created_at, "description": record.description,
        }
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        return d
