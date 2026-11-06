"""
M9 计量流水查询 API：GET /v1/usage-records（管理侧审计）

溯源：docs/arch/04 §2.2 GET /v1/usage-records 全量计量流水（审计）。
鉴权：require_superuser；过滤：主体/执行/资源类型；分页。
"""
from typing import Optional

from fastapi import APIRouter, Query

from base.common.permissions import require_superuser
from base.common.response import success_response
from base.common.quota.models.quota import UsageRecord

usage_record_router = APIRouter(prefix="/v1/usage-records", tags=["计量流水"])


@usage_record_router.get("", summary="计量流水分页查询")
async def list_usage_records(
    owner_type: Optional[str] = Query(None, description="主体类型: cus/usr"),
    owner_id: Optional[int] = Query(None, gt=0, description="主体 ID"),
    execution_id: Optional[int] = Query(None, gt=0, description="执行实例 ID"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    query = UsageRecord.all()
    if owner_type:
        query = query.filter(owner_type=owner_type)
    if owner_id:
        query = query.filter(owner_id=owner_id)
    if execution_id:
        query = query.filter(execution_id=execution_id)
    if resource_type:
        query = query.filter(resource_type=resource_type)

    total = await query.count()
    records = await query.offset((page - 1) * page_size).limit(page_size).order_by("-created_at")
    items = [
        {
            "id": r.id,
            "owner_type": r.owner_type,
            "owner_id": r.owner_id,
            "execution_id": r.execution_id,
            "node_id": r.node_id,
            "resource_type": r.resource_type,
            "amount": r.amount,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "cost": float(r.cost or 0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
    return success_response(data={
        "total": total, "page": page, "page_size": page_size, "items": items,
    })
