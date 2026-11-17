"""ContentOps 对外只读 OpenAPI 路由包（M4）。

- 路径前缀：/v1/contentops/openapi/*（随插件 route_prefix 装配）
- 鉴权：require_openapi_scope（专属 API Key，fail-closed + 限流 + 审计）
- 归属：继承 API Key 绑定的 CUS 租户，仅可见平台级 + 本租户规则
- 只读：不做任何写操作（不落命中记录），AI 改写/导出等写能力不对外开放
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from base.common.response import success_response
from base.plugins.contentops.services.compliance_service import ComplianceEngine
from base.plugins.contentops.services.openapi_auth import require_openapi_scope
from base.plugins.contentops.services.rule_service import RuleService

router = APIRouter(prefix="/openapi", tags=["内容合规开放API"])


class OpenapiCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, description="待检测文本")
    platform: Optional[str] = Field(None, description="目标平台（限定平台专属规则）")
    channel: str = Field(default="text", description="检测通道标识（text/ocr/asr）")


@router.post("/compliance/check", summary="[开放API] 文本合规检测")
async def openapi_check(
    data: OpenapiCheckRequest,
    ctx: dict = Depends(require_openapi_scope("compliance:check")),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    """外部第三方文本合规检测：复用平台级 + 租户规则，只读不落库。"""
    owner = ctx["owner"]
    rules = await ComplianceEngine.load_rules(owner, data.platform)
    hits = ComplianceEngine.detect_text(data.text, rules, channel=data.channel)
    summary = ComplianceEngine.aggregate(hits)
    return success_response(data={
        **summary,
        "hits": [h.to_dict() for h in hits],
        "platform": data.platform,
        "key_id": ctx["key_id"],
        "idempotency_key": idempotency_key,
    }, msg="检测完成")


@router.get("/rules", summary="[开放API] 可见规则查询")
async def openapi_rules(
    layer: Optional[str] = Query(None, description="规则层 L1-L4"),
    ctx: dict = Depends(require_openapi_scope("rules:read")),
):
    """外部第三方查询该租户可见规则（平台级 + 本租户 L4）。"""
    owner = ctx["owner"]
    items = await RuleService.list_rules(layer, owner)
    # 对外脱敏：规则表达式/依据可返回，但不暴露内部版本滚动以外的元数据
    return success_response(data={
        "items": items,
        "key_id": ctx["key_id"],
    })
