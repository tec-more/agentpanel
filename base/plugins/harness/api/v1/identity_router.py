"""Harness 外部身份映射管理（后台管理员）"""
from typing import Optional

from fastapi import APIRouter, Query

from base.common.permissions import require_superuser
from base.common.response import success_response, fail_response
from base.plugins.harness.models.harness import HarnessIdentity
from base.plugins.harness.schemas.harness import IdentityBind
from base.plugins.harness.services.identity_service import HarnessIdentityService

identity_router = APIRouter(prefix="/identities", tags=["Harness-身份映射"])


def _identity_dict(row: HarnessIdentity) -> dict:
    return {
        "id": row.id,
        "client_id": row.client_id,
        "external_type": row.external_type,
        "external_id": row.external_id,
        "external_name": row.external_name,
        "user_id": row.user_id,
        "owner_type": row.owner_type,
        "owner_id": row.owner_id,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@identity_router.post("", summary="绑定外部身份到本地用户")
async def bind_identity(payload: IdentityBind, admin_id: int = require_superuser()):
    identity = await HarnessIdentityService.bind(
        client_id=payload.client_id,
        external_type=payload.external_type,
        external_id=payload.external_id,
        user_id=payload.user_id,
        external_name=payload.external_name,
        owner_type=payload.owner_type,
        owner_id=payload.owner_id,
        meta=payload.meta,
    )
    return success_response(data=_identity_dict(identity), msg="绑定成功")


@identity_router.get("", summary="身份映射列表")
async def list_identities(
    client_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    query = HarnessIdentity.all()
    if client_id:
        query = query.filter(client_id=client_id)
    if user_id:
        query = query.filter(user_id=user_id)
    total = await query.count()
    rows = await query.offset((page - 1) * page_size).limit(page_size)
    return success_response(data={
        "total": total, "page": page, "page_size": page_size,
        "items": [_identity_dict(r) for r in rows],
    })


@identity_router.delete("/{identity_id}", summary="禁用身份映射")
async def disable_identity(identity_id: int, admin_id: int = require_superuser()):
    ok = await HarnessIdentityService.disable(identity_id)
    if not ok:
        return fail_response(msg="映射不存在", code=404, status_code=404)
    return success_response(msg="已禁用")
