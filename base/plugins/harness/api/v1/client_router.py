"""Harness 客户端凭据管理（后台管理员）"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from base.common.permissions import require_superuser
from base.common.response import success_response, fail_response
from base.plugins.harness.schemas.harness import ClientCreate
from base.plugins.harness.services.client_service import HarnessClientService

client_router = APIRouter(prefix="/clients", tags=["Harness-客户端"])


def _client_dict(client, secret: Optional[str] = None) -> dict:
    data = {
        "id": client.id,
        "client_id": client.client_id,
        "name": client.name,
        "status": client.status,
        "secret_prefix": client.secret_prefix,
        "scopes": client.scopes or [],
        "allowed_ips": client.allowed_ips,
        "expires_at": client.expires_at.isoformat() if client.expires_at else None,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "description": client.description,
    }
    if secret:
        data["secret"] = secret
        data["notice"] = "secret 仅此一次回显，请立即保存"
    return data


@client_router.post("", summary="签发 Harness 客户端凭据")
async def create_client(payload: ClientCreate, admin_id: int = require_superuser()):
    expires_at = datetime.fromisoformat(payload.expires_at) if payload.expires_at else None
    client, secret = await HarnessClientService.issue(
        name=payload.name,
        scopes=payload.scopes,
        allowed_ips=payload.allowed_ips,
        expires_at=expires_at,
        created_by=admin_id,
        description=payload.description,
    )
    return success_response(data=_client_dict(client, secret), msg="凭据签发成功")


@client_router.get("", summary="Harness 客户端列表")
async def list_clients(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    from base.plugins.harness.models.harness import HarnessClient

    query = HarnessClient.all()
    if status_filter:
        query = query.filter(status=status_filter)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size)
    return success_response(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_client_dict(c) for c in rows],
    })


@client_router.post("/{client_id}/revoke", summary="吊销 Harness 客户端凭据")
async def revoke_client(client_id: str, admin_id: int = require_superuser()):
    ok = await HarnessClientService.revoke(client_id)
    if not ok:
        return fail_response(msg="客户端不存在", code=404, status_code=404)
    return success_response(msg="已吊销")
