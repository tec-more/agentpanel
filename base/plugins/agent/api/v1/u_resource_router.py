"""
用户侧资源授权清单 API（cus 主体）

溯源：T11 节点2 §3 接口契约；docs/arch/04 §2.1 落地映射备注。
职责：为画布节点配置的资源选择器提供"当前主体已授权"资源清单。

边界：
- 仅返回已授权（effect=allow 且未过期）资源；不做 grant/revoke（属管理侧）。
- 授权判定权威仍在服务端保存期 E-110 与运行时 require_resource，本接口仅为选择器视图。
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from base.common.authz import OwnerContext, require_owner
from base.common.authz.constants import NODE_TYPE_LABELS
from base.common.authz.service import ResourceGrantService
from base.common.response import success_response

router = APIRouter(prefix="/u/resources", tags=["用户侧资源授权"])

# 资源类型枚举（与 graph_validator._NODE_RESOURCE_REFS 一致）
RESOURCE_TYPES = ("model", "kb", "tool", "agent", "node_type")

# node_type 受限类型中文名（常量已上移至 authz.constants，供管理侧授权 API 复用）
_NODE_TYPE_LABELS = NODE_TYPE_LABELS


def _to_int_ids(resource_ids: List[str]) -> List[int]:
    """将字符串 resource_id 安全转 int（脏数据跳过，不阻断）"""
    out: List[int] = []
    for rid in resource_ids:
        try:
            out.append(int(rid))
        except (TypeError, ValueError):
            continue
    return out


async def _load_metadata(resource_type: str, resource_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    按类型批量加载资源元数据，返回 {resource_id_str: {label, extra}}
    资源已删除/不可用的不返回（前端选择器自然隐藏，E-110 兜底）。
    """
    int_ids = _to_int_ids(resource_ids)
    if not int_ids:
        return {}
    result: Dict[str, Dict[str, Any]] = {}

    if resource_type == "model":
        from base.plugins.llm.models.model import LLMModel
        rows = await LLMModel.filter(id__in=int_ids, status="active").prefetch_related("provider")
        for m in rows:
            provider_name = getattr(getattr(m, "provider", None), "name", "") if hasattr(m, "provider") else ""
            result[str(m.id)] = {"label": m.model_name, "extra": {"provider": provider_name}}

    elif resource_type == "kb":
        from ...models.rag import RAGKnowledgeBase
        rows = await RAGKnowledgeBase.filter(id__in=int_ids, status="active")
        for kb in rows:
            result[str(kb.id)] = {"label": kb.name, "extra": {"status": kb.status}}

    elif resource_type == "tool":
        from ...models.tool import Tool
        rows = await Tool.filter(id__in=int_ids).prefetch_related("tags")
        for t in rows:
            try:
                tags = [tag.name for tag in t.tags] if hasattr(t, "tags") else []
            except Exception:
                tags = []
            result[str(t.id)] = {"label": t.display_name, "extra": {"tag": tags}}

    elif resource_type == "agent":
        from ...models.agent import Agent
        rows = await Agent.filter(id__in=int_ids, status="active")
        for a in rows:
            result[str(a.id)] = {"label": a.name, "extra": {}}

    elif resource_type == "node_type":
        # node_type 为静态类型编码，无表 join；label 取映射
        for rid in resource_ids:
            result[rid] = {"label": _NODE_TYPE_LABELS.get(rid, rid), "extra": {}}

    return result


@router.get("", summary="当前主体已授权资源清单")
async def list_my_resources(
    type: str = Query(..., description="资源类型: model/kb/tool/agent/node_type"),
    owner: OwnerContext = Depends(require_owner),
):
    if type not in RESOURCE_TYPES:
        return success_response(data={"items": []}, msg="未知资源类型")
    grants = await ResourceGrantService.list_by_subject(
        owner, resource_type=type, only_valid=True
    )
    resource_ids = [g.resource_id for g in grants]
    metadata = await _load_metadata(type, resource_ids)
    items = []
    for g in grants:
        meta = metadata.get(g.resource_id)
        if meta is None:
            # 资源已删除/不可用：不返回（选择器隐藏；E-110 保存时权威兜底）
            continue
        items.append({
            "id": g.resource_id,
            "label": meta["label"],
            "extra": meta["extra"],
            "expires_at": g.expires_at.isoformat() if getattr(g, "expires_at", None) else None,
        })
    return success_response(data={"items": items})
