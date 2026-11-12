"""
M9 计量流水查询 API：GET /v1/usage-records（管理侧审计）

溯源：docs/arch/04 §2.2 GET /v1/usage-records 全量计量流水（审计）。
鉴权：
- 读权限 quota:org:view / quota:org:manage
- 非管理员仅能查看自己所属组织的流水；越权组织/成员返回 403（不是空列表）
过滤：主体/组织成员/来源/usage_kind/资源类型/时间范围；分页。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from base.common.permissions import require_any_permission
from base.common.response import success_response
from base.common.quota.models.quota import UsageRecord
from base.common.quota.services.org_scope import resolve_user_org_ids
from base.common.plugin_symbol import resolve_plugin_symbol

usage_record_router = APIRouter(prefix="/v1/usage-records", tags=["计量流水"])

_view_access = require_any_permission("quota:org:view", "quota:org:manage")


@usage_record_router.get("", summary="计量流水分页查询")
async def list_usage_records(
    owner_type: Optional[str] = Query(None, description="主体类型: cus/usr/org"),
    owner_id: Optional[int] = Query(None, gt=0, description="主体 ID"),
    member_id: Optional[int] = Query(None, gt=0, description="成员 ID（组织配额拆分）"),
    execution_id: Optional[int] = Query(None, gt=0, description="执行实例 ID"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    source: Optional[str] = Query(None, description="用量来源: provider/gateway/estimated/legacy"),
    usage_kind: Optional[str] = Query(None, description="用量类型: normal/compaction/subagent"),
    start_time: Optional[datetime] = Query(None, description="起始时间（含）"),
    end_time: Optional[datetime] = Query(None, description="结束时间（含）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: int = _view_access,
):
    scope = await resolve_user_org_ids(user_id)
    query = UsageRecord.all()

    if scope is not None:
        # 非管理员：只允许组织主体，且组织必须在授权集合内；显式越权直接 403
        if owner_type and owner_type != "org":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="非管理员仅能查看所属组织的计量流水",
            )
        if owner_id is not None and int(owner_id) not in scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权访问组织 {owner_id} 的计量流水",
            )
        query = query.filter(owner_type="org", owner_id__in=list(scope))
        if member_id is not None:
            CustomerOrganizationMember = resolve_plugin_symbol(
                "base.plugins.customer.models.customer_organization.CustomerOrganizationMember"
            )

            member_ok = await CustomerOrganizationMember.filter(
                customer_id=member_id, org_id__in=list(scope)
            ).exists()
            if not member_ok:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无权访问成员 {member_id} 的计量流水",
                )
    else:
        if owner_type:
            query = query.filter(owner_type=owner_type)
        if owner_id:
            query = query.filter(owner_id=owner_id)

    if member_id:
        query = query.filter(member_id=member_id)
    if execution_id:
        query = query.filter(execution_id=execution_id)
    if resource_type:
        query = query.filter(resource_type=resource_type)
    if source:
        query = query.filter(source=source)
    if usage_kind:
        query = query.filter(usage_kind=usage_kind)
    if start_time:
        query = query.filter(created_at__gte=start_time)
    if end_time:
        query = query.filter(created_at__lte=end_time)

    total = await query.count()
    records = await query.offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    items = [
        {
            "id": r.id,
            "owner_type": r.owner_type,
            "owner_id": r.owner_id,
            "member_id": r.member_id,
            "execution_id": r.execution_id,
            "node_id": r.node_id,
            "resource_type": r.resource_type,
            "amount": r.amount,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "cost": float(r.cost or 0),
            "source": r.source,
            "usage_kind": r.usage_kind,
            "model": r.model,
            "provider": r.provider,
            "cache_read_tokens": r.cache_read_tokens,
            "cache_write_tokens": r.cache_write_tokens,
            "session_ref": r.session_ref,
            "gateway_key": r.gateway_key,
            "price_snapshot": r.price_snapshot,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
    return success_response(data={
        "total": total, "page": page, "page_size": page_size, "items": items,
    })
