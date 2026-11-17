"""客户内容工作台 API（M5）：/workspace/*（全部强制 CUS 主体）。

让外部客户在自助前端里直接做内容合规自检：复用 contentops 的合规引擎，
规则来源 = 平台级规则 + 该 CUS 租户可见规则（由 load_rules(owner) 保证归属过滤），
与客户在后台内容工作台看到的结果口径一致，但严格只读、不落库、不接收内容 ID。

边界：customer 插件只依赖 contentops 的 service（插件间横向调用，签名稳定）；
不把 contentops 的路由/模型挂进 customer，避免双重装配。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from base.common.authz.context import OwnerContext
from base.common.response import success_response
from base.plugins.customer.services.cus_guard import require_customer

workspace_router = APIRouter(prefix="/workspace", tags=["客户内容工作台"])


class CustomerCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000, description="待检测文本")
    platform: Optional[str] = Field(None, description="目标平台（限定平台专属规则）")
    channel: str = Field(default="text", description="检测通道标识（text/ocr/asr）")


@workspace_router.post("/compliance/check", summary="[客户工作台] 文本合规自检")
async def workspace_compliance_check(
    data: CustomerCheckRequest,
    owner: OwnerContext = Depends(require_customer),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """客户自助合规检测：平台规则 + 本租户规则，只读不落库。"""
    from base.plugins.contentops.services.compliance_service import ComplianceEngine

    rules = await ComplianceEngine.load_rules(owner, data.platform)
    hits = ComplianceEngine.detect_text(data.text, rules, channel=data.channel)
    summary = ComplianceEngine.aggregate(hits)
    return success_response(data={
        **summary,
        "hits": [h.to_dict() for h in hits],
        "platform": data.platform,
        "idempotency_key": idempotency_key,
    })


@workspace_router.get("/rules", summary="[客户工作台] 我可见的合规规则")
async def workspace_rules(
    layer: Optional[str] = Query(None, description="规则层 L1-L4"),
    owner: OwnerContext = Depends(require_customer),
):
    """展示当前客户可见的规则（平台级 + 本租户），供客户理解检测依据。"""
    from base.plugins.contentops.services.rule_service import RuleService

    items = await RuleService.list_rules(layer, owner)
    return success_response(data={"items": items})
