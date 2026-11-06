"""
管理侧资源授权管理 API

溯源：T11 节点2 §3 接口契约；资源授权管理 PRD（docs/RequirementsAnalysis/resource-grant-admin-prd.md）
与技术方案（docs/arch/resource-grant-admin-tech.md，节点1 裁定：数据源端点聚合到本域）。
鉴权：require_superuser（沿用 T3/quota admin 惯例）。

职责：授权记录列表/按主体反查/单条与批量发放/撤销/资源反查 + 主体与资源选择器数据源。
授权四元组唯一（T1 约束），grant/revoke 幂等；批量发放逐条独立（PRD §6.4），不整体回滚。
组织维度（§6.1）：owner_type 支持 org，判定扩展见 base/common/authz/service.py。
审计：grant/revoke 写 audit（ORM create/update/delete 由审计插件自动捕获）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from tortoise.expressions import Q

from base.common.authz.constants import NODE_TYPE_LABELS
from base.common.authz.models.resource_grant import ResourceGrant
from base.common.authz.service import ResourceGrantService, is_subject_active
from base.common.permissions import require_superuser
from base.common.response import fail_response, success_response

router = APIRouter(prefix="/admin/grants", tags=["资源授权管理"])

RESOURCE_TYPES = ("model", "kb", "tool", "agent", "node_type")
OWNER_TYPES = ("cus", "usr", "org")

_OWNER_TYPE_LABELS = {"cus": "客户", "usr": "后台用户", "org": "客户组织"}
_RESOURCE_TYPE_LABELS = {
    "model": "模型", "kb": "知识库", "tool": "工具", "agent": "智能体", "node_type": "节点类型",
}
# 选择器数据源单页上限（资源/主体选项不设翻页，关键词搜索）
_OPTIONS_LIMIT = 50
_KEYWORD_MATCH_LIMIT = 200


class SubjectItem(BaseModel):
    owner_type: str = Field(..., description="主体类型: cus/usr/org")
    owner_id: int = Field(..., gt=0, description="主体 ID")


class GrantSchema(BaseModel):
    owner_type: str = Field(..., description="主体类型: cus/usr/org")
    owner_id: int = Field(..., gt=0, description="主体 ID")
    resource_type: str = Field(..., description="资源类型")
    resource_id: str = Field(..., min_length=1, max_length=64, description="资源 ID（与模型层 max_length=64 一致）")
    expires_at: Optional[str] = Field(None, description="过期时间 ISO（可选，须晚于当前时间）")


class BatchGrantSchema(BaseModel):
    resource_type: str = Field(..., description="资源类型")
    resource_id: str = Field(..., min_length=1, max_length=64, description="资源 ID（与模型层 max_length=64 一致）")
    subjects: List[SubjectItem] = Field(..., min_length=1, max_length=100, description="主体列表（逐条独立）")
    expires_at: Optional[str] = Field(None, description="过期时间 ISO（可选，须晚于当前时间）")


def _valid_type(resource_type: str) -> bool:
    return resource_type in RESOURCE_TYPES


def _valid_owner(owner_type: str) -> bool:
    return owner_type in OWNER_TYPES


async def _resource_exists(resource_type: str, resource_id: str) -> bool:
    """FR-03/测试节点2 OB-1：资源有效性校验——存在且处于可授权状态（active/未停用）"""
    meta = await _load_resource_meta_all(resource_type, [resource_id])
    info = meta.get(resource_id)
    return bool(info) and not info.get("inactive", False)


def _parse_expires(expires_at: Optional[str]):
    """解析过期时间；格式非法返回 'invalid'，未晚于当前时间返回 'past'（FR-03 校验）

    时区：前端 el-date-picker 输出无时区 ISO（本地时间），存储为 UTC aware；
    naive 输入按系统本地时区解释并转 aware，避免 UTC 回读产生 8 小时语义偏差。
    """
    if not expires_at:
        return None
    try:
        parsed = datetime.fromisoformat(expires_at)
    except (ValueError, TypeError):
        return "invalid"
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    from datetime import timezone as _tz
    if parsed <= datetime.now(_tz.utc):
        return "past"
    return parsed


def _grant_status(record: ResourceGrant) -> str:
    if record.expires_at is None:
        return "valid"
    expires = record.expires_at
    now = datetime.now(expires.tzinfo) if expires.tzinfo else datetime.now()
    return "valid" if expires > now else "expired"


def _to_int_ids(resource_ids: List[str]) -> List[int]:
    out: List[int] = []
    for rid in resource_ids:
        try:
            out.append(int(rid))
        except (TypeError, ValueError):
            continue
    return out


# ---------- 元数据加载（enrich 与选择器共用；含已删除资源，供"资源已删除"标注） ----------

async def _load_resource_meta_all(resource_type: str, resource_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    按类型批量加载资源元数据（含已删除/停用），返回 {resource_id_str: {label, deleted}}。
    与 u_resource_router._load_metadata 的差异：不过滤不可用资源，以 deleted 标注（§6.2 保留标注）。
    """
    int_ids = _to_int_ids(resource_ids)
    result: Dict[str, Dict[str, Any]] = {}

    if resource_type == "node_type":
        # 静态类型编码，无表；编码不在受限映射内视为已删除
        for rid in resource_ids:
            if rid in NODE_TYPE_LABELS:
                result[rid] = {"label": NODE_TYPE_LABELS[rid], "inactive": False}
        return result

    if not int_ids:
        return result

    # D4 修复：deleted（库中不存在）与 inactive（存在但停用/禁用）分开标注，避免语义误导
    if resource_type == "model":
        from base.plugins.llm.models.model import LLMModel
        rows = await LLMModel.filter(id__in=int_ids).prefetch_related("provider")
        for m in rows:
            provider_name = getattr(getattr(m, "provider", None), "name", "") if hasattr(m, "provider") else ""
            result[str(m.id)] = {
                "label": m.model_name,
                "inactive": getattr(m, "status", "active") != "active",
                "extra": {"provider": provider_name},
            }
    elif resource_type == "kb":
        from ...models.rag import RAGKnowledgeBase
        rows = await RAGKnowledgeBase.filter(id__in=int_ids)
        for kb in rows:
            result[str(kb.id)] = {
                "label": kb.name,
                "inactive": getattr(kb, "status", "active") != "active",
                "extra": {"status": kb.status},
            }
    elif resource_type == "tool":
        from ...models.tool import Tool
        rows = await Tool.filter(id__in=int_ids)
        for t in rows:
            result[str(t.id)] = {
                "label": t.display_name,
                "inactive": not getattr(t, "enabled", True),
                "extra": {},
            }
    elif resource_type == "agent":
        from ...models.agent import Agent
        rows = await Agent.filter(id__in=int_ids)
        for a in rows:
            result[str(a.id)] = {
                "label": a.name,
                "inactive": getattr(a, "status", "active") != "active",
                "extra": {"status": a.status},
            }
    return result


async def _load_owner_labels(owner_type: str, owner_ids: List[int]) -> Dict[int, str]:
    """批量加载主体显示名：cus→昵称/用户名；usr→用户名；org→组织名"""
    if not owner_ids:
        return {}
    labels: Dict[int, str] = {}
    if owner_type == "cus":
        from base.plugins.customer.models.customer import Customer
        rows = await Customer.filter(id__in=owner_ids)
        for c in rows:
            labels[c.id] = c.nickname or c.username or f"客户#{c.id}"
    elif owner_type == "usr":
        from base.core.users.models.users import User
        rows = await User.filter(id__in=owner_ids)
        for u in rows:
            labels[u.id] = u.username or f"用户#{u.id}"
    elif owner_type == "org":
        from base.plugins.customer.models.customer_organization import CustomerOrganization
        rows = await CustomerOrganization.filter(id__in=owner_ids)
        for o in rows:
            labels[o.id] = o.name or f"组织#{o.id}"
    return labels


async def _enrich_grants(records: List[ResourceGrant]) -> List[Dict[str, Any]]:
    """授权记录 enrich：主体显示名 + 资源显示名 + 资源已删除标注（§6.2）+ 授权状态"""
    # 按类型聚合 id，分批加载避免 N+1
    res_ids_by_type: Dict[str, Set[str]] = {}
    owner_ids_by_type: Dict[str, Set[int]] = {}
    for r in records:
        res_ids_by_type.setdefault(r.resource_type, set()).add(r.resource_id)
        owner_ids_by_type.setdefault(r.owner_type, set()).add(r.owner_id)

    res_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for rtype, ids in res_ids_by_type.items():
        res_meta[rtype] = await _load_resource_meta_all(rtype, list(ids))
    owner_labels: Dict[str, Dict[int, str]] = {}
    for otype, ids in owner_ids_by_type.items():
        owner_labels[otype] = await _load_owner_labels(otype, list(ids))

    items = []
    for r in records:
        meta = res_meta.get(r.resource_type, {}).get(r.resource_id)
        items.append({
            "id": r.id,
            "owner_type": r.owner_type,
            "owner_type_label": _OWNER_TYPE_LABELS.get(r.owner_type, r.owner_type),
            "owner_id": r.owner_id,
            "owner_label": owner_labels.get(r.owner_type, {}).get(r.owner_id, f"#{r.owner_id}"),
            "resource_type": r.resource_type,
            "resource_type_label": _RESOURCE_TYPE_LABELS.get(r.resource_type, r.resource_type),
            "resource_id": r.resource_id,
            "resource_label": meta["label"] if meta else r.resource_id,
            "resource_deleted": meta is None,
            "resource_inactive": bool(meta and meta.get("inactive")),
            "granted_by": getattr(r, "granted_by", ""),
            "expires_at": r.expires_at.isoformat() if getattr(r, "expires_at", None) else None,
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
            "status": _grant_status(r),
        })
    return items


async def _search_resource_ids(resource_type: Optional[str], keyword: str) -> Set[str]:
    """关键词命中资源名称 → resource_id 集合（FR-07 关键词筛选的 DB 侧前置解析）"""
    matched: Set[str] = set()
    types = [resource_type] if resource_type else list(RESOURCE_TYPES)
    for rtype in types:
        if rtype == "node_type":
            matched |= {code for code, label in NODE_TYPE_LABELS.items()
                        if keyword.lower() in code.lower() or keyword in label}
            continue
        try:
            if rtype == "model":
                from base.plugins.llm.models.model import LLMModel
                ids = await LLMModel.filter(model_name__icontains=keyword).limit(_KEYWORD_MATCH_LIMIT).values_list("id", flat=True)
            elif rtype == "kb":
                from ...models.rag import RAGKnowledgeBase
                ids = await RAGKnowledgeBase.filter(name__icontains=keyword).limit(_KEYWORD_MATCH_LIMIT).values_list("id", flat=True)
            elif rtype == "tool":
                from ...models.tool import Tool
                ids = await Tool.filter(display_name__icontains=keyword).limit(_KEYWORD_MATCH_LIMIT).values_list("id", flat=True)
            elif rtype == "agent":
                from ...models.agent import Agent
                ids = await Agent.filter(name__icontains=keyword).limit(_KEYWORD_MATCH_LIMIT).values_list("id", flat=True)
            else:
                continue
            matched |= {str(i) for i in ids}
        except Exception:
            continue  # 单类型查询失败不阻断整体筛选
    return matched


async def _search_owner_ids(owner_type: Optional[str], keyword: str) -> Set[int]:
    """关键词命中主体名称 → owner_id 集合"""
    matched: Set[int] = set()
    types = [owner_type] if owner_type else list(OWNER_TYPES)
    for otype in types:
        try:
            if otype == "cus":
                from base.plugins.customer.models.customer import Customer
                ids = await Customer.filter(
                    Q(username__icontains=keyword) | Q(nickname__icontains=keyword) | Q(email__icontains=keyword)
                ).limit(_KEYWORD_MATCH_LIMIT).values_list("id", flat=True)
            elif otype == "usr":
                from base.core.users.models.users import User
                ids = await User.filter(
                    Q(username__icontains=keyword) | Q(email__icontains=keyword)
                ).limit(_KEYWORD_MATCH_LIMIT).values_list("id", flat=True)
            elif otype == "org":
                from base.plugins.customer.models.customer_organization import CustomerOrganization
                ids = await CustomerOrganization.filter(name__icontains=keyword).limit(_KEYWORD_MATCH_LIMIT).values_list("id", flat=True)
            else:
                continue
            matched |= set(ids)
        except Exception:
            continue
    return matched


# ==================== 授权管理端点 ====================

@router.post("", summary="发放授权（幂等）")
async def grant_resource(data: GrantSchema, admin_id: int = require_superuser()):
    if not _valid_type(data.resource_type):
        return fail_response(msg=f"非法资源类型: {data.resource_type}")
    if not _valid_owner(data.owner_type):
        return fail_response(msg=f"非法主体类型: {data.owner_type}（支持 cus/usr/org）")
    parsed = _parse_expires(data.expires_at)
    if parsed == "invalid":
        return fail_response(msg="过期时间格式非法，需为 ISO 8601")
    if parsed == "past":
        return fail_response(msg="过期时间必须晚于当前时间")
    # §6.3：仅允许向有效主体授权
    if not await is_subject_active(data.owner_type, data.owner_id):
        return fail_response(msg="主体不存在或已禁用，无法授权")
    # OB-1：仅允许向有效资源授权（存在且未停用/删除）
    if not await _resource_exists(data.resource_type, data.resource_id):
        return fail_response(msg="资源不存在或已停用，无法授权")
    record = await ResourceGrantService.grant(
        (data.owner_type, data.owner_id),
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        granted_by=f"admin:{admin_id}",
        expires_at=parsed,
    )
    return success_response(data=_grant_to_dict(record), msg="授权成功")


@router.delete("", summary="撤销授权（幂等）")
async def revoke_resource(data: GrantSchema, admin_id: int = require_superuser()):
    if not _valid_type(data.resource_type):
        return fail_response(msg=f"非法资源类型: {data.resource_type}")
    if not _valid_owner(data.owner_type):
        return fail_response(msg=f"非法主体类型: {data.owner_type}（支持 cus/usr/org）")
    deleted = await ResourceGrantService.revoke(
        (data.owner_type, data.owner_id),
        resource_type=data.resource_type,
        resource_id=data.resource_id,
    )
    return success_response(data={"deleted": deleted}, msg="撤销成功" if deleted else "记录本不存在")


@router.get("", summary="按资源反查被授权主体")
async def list_grants_by_resource(
    resource_type: str = Query(...),
    resource_id: str = Query(...),
    admin_id: int = require_superuser(),
):
    if not _valid_type(resource_type):
        return fail_response(msg=f"非法资源类型: {resource_type}")
    records = await ResourceGrantService.list_by_resource(resource_type, resource_id)
    return success_response(data={"items": await _enrich_grants(records)})


@router.get("/list", summary="授权记录分页列表（FR-02/FR-07）")
async def list_grants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    resource_type: Optional[str] = Query(None),
    owner_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="valid/expired"),
    keyword: Optional[str] = Query(None, description="资源名称/主体名称关键词"),
    admin_id: int = require_superuser(),
):
    if resource_type and not _valid_type(resource_type):
        return fail_response(msg=f"非法资源类型: {resource_type}")
    if owner_type and not _valid_owner(owner_type):
        return fail_response(msg=f"非法主体类型: {owner_type}（支持 cus/usr/org）")

    query = ResourceGrant.all()
    if resource_type:
        query = query.filter(resource_type=resource_type)
    if owner_type:
        query = query.filter(owner_type=owner_type)
    if status == "valid":
        query = query.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=datetime.now()))
    elif status == "expired":
        query = query.filter(expires_at__not_isnull=True, expires_at__lte=datetime.now())
    if keyword:
        keyword = keyword.strip()
        if keyword:
            res_ids = await _search_resource_ids(resource_type, keyword)
            owner_ids = await _search_owner_ids(owner_type, keyword)
            if not res_ids and not owner_ids:
                return success_response(data={"items": [], "total": 0})
            query = query.filter(Q(resource_id__in=list(res_ids)) | Q(owner_id__in=list(owner_ids)))

    total = await query.count()
    records = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)
    return success_response(data={"items": await _enrich_grants(records), "total": total})


@router.get("/by-subject", summary="按主体反查授权清单（FR-07）")
async def list_grants_by_subject(
    owner_type: str = Query(...),
    owner_id: int = Query(..., gt=0),
    admin_id: int = require_superuser(),
):
    if not _valid_owner(owner_type):
        return fail_response(msg=f"非法主体类型: {owner_type}（支持 cus/usr/org）")
    # cus 主体返回合并组织授权后的完整视图（与判定语义一致）
    records = await ResourceGrantService.list_by_subject(
        (owner_type, owner_id), only_valid=False
    )
    return success_response(data={"items": await _enrich_grants(records)})


@router.post("/batch", summary="批量发放授权（单资源多主体，逐条独立 FR-03/§6.4）")
async def batch_grant(data: BatchGrantSchema, admin_id: int = require_superuser()):
    if not _valid_type(data.resource_type):
        return fail_response(msg=f"非法资源类型: {data.resource_type}")
    parsed = _parse_expires(data.expires_at)
    if parsed == "invalid":
        return fail_response(msg="过期时间格式非法，需为 ISO 8601")
    if parsed == "past":
        return fail_response(msg="过期时间必须晚于当前时间")
    # OB-1：仅允许向有效资源授权（存在且未停用/删除）
    if not await _resource_exists(data.resource_type, data.resource_id):
        return fail_response(msg="资源不存在或已停用，无法授权")

    succeeded: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    for subject in data.subjects:
        if not _valid_owner(subject.owner_type):
            failed.append({"owner_type": subject.owner_type, "owner_id": subject.owner_id,
                           "reason": f"非法主体类型: {subject.owner_type}"})
            continue
        if not await is_subject_active(subject.owner_type, subject.owner_id):
            failed.append({"owner_type": subject.owner_type, "owner_id": subject.owner_id,
                           "reason": "主体不存在或已禁用"})
            continue
        try:
            existing = await ResourceGrant.get_or_none(
                owner_type=subject.owner_type, owner_id=subject.owner_id,
                resource_type=data.resource_type, resource_id=data.resource_id,
            )
            await ResourceGrantService.grant(
                (subject.owner_type, subject.owner_id),
                resource_type=data.resource_type,
                resource_id=data.resource_id,
                granted_by=f"admin:{admin_id}",
                expires_at=parsed,
            )
            succeeded.append({"owner_type": subject.owner_type, "owner_id": subject.owner_id,
                              "created": existing is None})
        except Exception as exc:
            failed.append({"owner_type": subject.owner_type, "owner_id": subject.owner_id,
                           "reason": str(exc)[:200]})
    return success_response(
        data={"succeeded": succeeded, "failed": failed},
        msg=f"成功 {len(succeeded)} 条，失败 {len(failed)} 条",
    )


# ==================== 选择器数据源端点（节点1 裁定 Q1：聚合到本域） ====================

@router.get("/subjects", summary="主体选择器数据源（仅有效主体，§6.3）")
async def list_subject_options(
    type: str = Query(..., description="主体类型: cus/usr/org"),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_id: int = require_superuser(),
):
    if not _valid_owner(type):
        return fail_response(msg=f"非法主体类型: {type}（支持 cus/usr/org）")
    keyword = (keyword or "").strip()

    if type == "cus":
        from base.plugins.customer.models.customer import Customer
        query = Customer.filter(is_active=True)
        if keyword:
            query = query.filter(Q(username__icontains=keyword) | Q(nickname__icontains=keyword) | Q(email__icontains=keyword))
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        items = [{"id": c.id, "label": c.nickname or c.username or f"客户#{c.id}",
                  "extra": {"username": c.username, "email": c.email}} for c in rows]
    elif type == "usr":
        from base.core.users.models.users import User
        query = User.filter(is_active=True)
        if keyword:
            query = query.filter(Q(username__icontains=keyword) | Q(email__icontains=keyword))
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        items = [{"id": u.id, "label": u.username or f"用户#{u.id}",
                  "extra": {"email": getattr(u, "email", "")}} for u in rows]
    else:  # org
        from base.plugins.customer.models.customer_organization import CustomerOrganization
        query = CustomerOrganization.filter(status="active")
        if keyword:
            query = query.filter(name__icontains=keyword)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size)
        items = [{"id": o.id, "label": o.name or f"组织#{o.id}", "extra": {}} for o in rows]

    return success_response(data={"items": items, "total": total})


@router.get("/resource-options", summary="资源选择器数据源（仅可授权资源，FR-05）")
async def list_resource_options(
    type: str = Query(..., description="资源类型: model/kb/tool/agent/node_type"),
    keyword: Optional[str] = Query(None),
    admin_id: int = require_superuser(),
):
    if not _valid_type(type):
        return fail_response(msg=f"非法资源类型: {type}")
    keyword = (keyword or "").strip()
    items: List[Dict[str, Any]] = []

    if type == "node_type":
        for code, label in NODE_TYPE_LABELS.items():
            if keyword and keyword.lower() not in code.lower() and keyword not in label:
                continue
            items.append({"id": code, "label": label, "extra": {"code": code}})
    elif type == "model":
        from base.plugins.llm.models.model import LLMModel
        query = LLMModel.filter(status="active")
        if keyword:
            query = query.filter(model_name__icontains=keyword)
        rows = await query.order_by("-id").limit(_OPTIONS_LIMIT).prefetch_related("provider")
        for m in rows:
            provider_name = getattr(getattr(m, "provider", None), "name", "") if hasattr(m, "provider") else ""
            items.append({"id": str(m.id), "label": m.model_name, "extra": {"provider": provider_name}})
    elif type == "kb":
        from ...models.rag import RAGKnowledgeBase
        query = RAGKnowledgeBase.filter(status="active")
        if keyword:
            query = query.filter(name__icontains=keyword)
        rows = await query.order_by("-id").limit(_OPTIONS_LIMIT)
        items = [{"id": str(kb.id), "label": kb.name, "extra": {"status": kb.status}} for kb in rows]
    elif type == "tool":
        from ...models.tool import Tool
        # OB-3：仅可授权资源（FR-05），过滤禁用工具
        query = Tool.filter(enabled=True)
        if keyword:
            query = query.filter(display_name__icontains=keyword)
        rows = await query.order_by("-id").limit(_OPTIONS_LIMIT)
        items = [{"id": str(t.id), "label": t.display_name, "extra": {}} for t in rows]
    elif type == "agent":
        from ...models.agent import Agent
        query = Agent.filter(status="active")
        if keyword:
            query = query.filter(name__icontains=keyword)
        rows = await query.order_by("-id").limit(_OPTIONS_LIMIT)
        items = [{"id": str(a.id), "label": a.name, "extra": {"status": a.status}} for a in rows]

    return success_response(data={"items": items})


def _grant_to_dict(record) -> dict:
    return {
        "id": record.id,
        "owner_type": record.owner_type,
        "owner_id": record.owner_id,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "effect": getattr(record, "effect", "allow"),
        "granted_by": getattr(record, "granted_by", ""),
        "expires_at": record.expires_at.isoformat() if getattr(record, "expires_at", None) else None,
    }
