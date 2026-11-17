"""对外 API Key 管理路由（M4，登录态）。

- 租户管理员为「自己租户」签发/吊销对外 OpenAPI Key；
- owner 强制从 JWT 上下文注入，不接受客户端传入 owner_type/owner_id；
- 复用 contentops:rule:manage 权限码（同属系统配置管理，避免扩 12 码全集）。
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from base.common.authz import OwnerContext, require_owner, require_action
from base.common.response import success_response, fail_response
from base.plugins.contentops.models import ContentopsApiKey
from base.plugins.contentops.schemas.content_schema import ApiKeyCreate
from base.plugins.contentops.services.api_key_service import (
    ContentopsApiKeyService, OPENAPI_SCOPES,
)

api_keys_router = APIRouter(prefix="/api-keys", tags=["开放API密钥"])


@api_keys_router.post("", summary="签发对外 API Key")
async def issue_api_key(
    data: ApiKeyCreate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    # 非法 scope 直接拒绝，不静默降级为全集
    invalid = [s for s in data.scopes if s not in OPENAPI_SCOPES]
    if invalid:
        return fail_response(msg=f"非法 scope: {invalid}", code=400)
    expires = None
    if data.expires_at:
        try:
            expires = datetime.fromisoformat(data.expires_at)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
        except ValueError:
            return fail_response(msg="expires_at 格式非法", code=400)
    record, secret = await ContentopsApiKeyService.issue(
        name=data.name, owner_id=owner.owner_id, owner_type=owner.owner_type,
        scopes=data.scopes, allowed_ips=data.allowed_ips, expires_at=expires,
        rate_limit_rpm=data.rate_limit_rpm, created_by=user_id,
        description=data.description,
    )
    # secret 明文仅此一次回显
    return success_response(data={
        **ContentopsApiKeyService.to_safe_dict(record),
        "secret": secret,
    }, msg="请妥善保存 secret，此后再不回显")


@api_keys_router.get("", summary="列出本租户 API Key")
async def list_api_keys(
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:view"),
):
    rows = await ContentopsApiKey.filter(
        owner_type=owner.owner_type, owner_id=owner.owner_id,
    ).order_by("-created_at")
    return success_response(data={"items": [ContentopsApiKeyService.to_safe_dict(r) for r in rows]})


@api_keys_router.delete("/{key_id}", summary="吊销 API Key")
async def revoke_api_key(
    key_id: str,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    record = await ContentopsApiKey.get_or_none(key_id=key_id)
    if not record or record.owner_type != owner.owner_type or record.owner_id != owner.owner_id:
        return fail_response(msg="Key 不存在或无权操作", code=404)
    await ContentopsApiKeyService.revoke(key_id)
    return success_response(msg="已吊销")
