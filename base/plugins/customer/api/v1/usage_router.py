"""
用户侧计量流水查询 API：GET /v1/customer/usage-records（T14+ K3）

溯源：
- docs/arch/04 §2.2 GET /v1/usage-records（管理侧 require_superuser）；
- PRD §7.3：计量必须精确到"用户 + 工作流 + 节点"，用于账单与优化建议；
- T14+ 裁定（推翻 Q1-A）：用户侧亦需可见自身用量流水（归属过滤）。

挂载：customer 插件 route_prefix=/v1/customer（文件名 _router 结尾，插件加载器
优先注册，避免被 customer.py 的 /{customer_id} 参数化路由吞掉，同 quota_router.py）。
鉴权：require_owner（M8 双主体上下文）；服务层强制 owner 过滤，不接受客户端传入的
owner_type/owner_id，杜绝水平越权。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from base.common.authz.context import OwnerContext, require_owner
from base.common.response import success_response
from base.common.quota.models.quota import UsageRecord

usage_router = APIRouter(prefix="/usage-records", tags=["计量流水"])


@usage_router.get("", summary="当前主体用量流水（归属过滤 + 分页）")
async def list_my_usage_records(
    execution_id: Optional[int] = Query(None, gt=0, description="执行实例 ID"),
    resource_type: Optional[str] = Query(None, description="资源类型（llm_token/kb_search/vector_write/tool_call 等）"),
    start_time: Optional[datetime] = Query(None, description="起始时间（含，ISO 8601）"),
    end_time: Optional[datetime] = Query(None, description="结束时间（不含，ISO 8601）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    owner: OwnerContext = Depends(require_owner),
):
    """
    M8 归属过滤：强制按当前 token 主体过滤，不接受客户端 owner_* 入参；
    排序 created_at DESC, id DESC（与管理侧 usage.py 一致，便于对账）。
    """
    query = UsageRecord.filter(owner_type=owner.owner_type, owner_id=owner.owner_id)
    if execution_id:
        query = query.filter(execution_id=execution_id)
    if resource_type:
        query = query.filter(resource_type=resource_type)
    if start_time:
        query = query.filter(created_at__gte=start_time)
    if end_time:
        query = query.filter(created_at__lt=end_time)

    total = await query.count()
    records = (
        await query.order_by("-created_at", "-id")
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": r.id,
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
