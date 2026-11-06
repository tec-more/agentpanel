"""
M11 客户组织 管理侧 API（A3 裁剪版：只读 + 最小写）

溯源：资源授权管理 PRD §6.1；docs/arch/resource-grant-admin-tech.md §3.2（组织列表缺口）。
挂载：customer 插件 route_prefix=/v1/customer + 本文件 prefix=/admin/organizations
     → 最终路径 /v1/customer/admin/organizations/*；仅超级管理员可调用。
鉴权：require_superuser（与 agent/admin_grant_router 同一惯例）。

超管旁路：不改 organization_service._require_role、不给服务开后门；超管校验通过后
显式取组织 owner_customer_id 作为 operator 调用 CustomerOrganizationService 公开方法，
复用同一套 `authz:org_ids:` 缓存失效钩子（create_organization / add_member / remove_member）。
写操作一律经 service，本文件不直写 ORM。
"""
from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from base.common.authz.constants import NODE_TYPE_LABELS
from base.common.authz.service import ResourceGrantService
from base.common.permissions import require_superuser
from base.common.response import fail_response, success_response
from base.plugins.customer.services.organization_service import (
    CustomerOrganizationService,
    OrganizationError,
)

organization_admin_router = APIRouter(prefix="/admin/organizations", tags=["组织管理（后台）"])

_ORG_STATUSES = ("active", "disabled")
# 业务异常 → HTTP 状态码（组织不存在 404；重复成员/已是 owner/状态冲突 409；其余入参类 400）
_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "already_member": status.HTTP_409_CONFLICT,
    "cannot_remove_owner": status.HTTP_409_CONFLICT,
    "org_unavailable": status.HTTP_409_CONFLICT,
}


class CreateOrganizationSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="组织名称")
    owner_customer_id: int = Field(..., gt=0, description="组织所有者客户 ID")


class AddMemberSchema(BaseModel):
    customer_id: int = Field(..., gt=0, description="成员客户 ID")
    role: str = Field("member", description="成员角色: admin/member")


def _fail_from_error(exc: OrganizationError):
    return fail_response(msg=exc.message, status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST))


def _dt(value) -> Optional[str]:
    return value.isoformat() if value else None


# ---------- 资源 enrich（语义对齐 agent/admin_grant_router._load_resource_meta_all） ----------

async def _load_resource_meta(resource_type: str, resource_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """批量加载资源元数据（含已删除/已停用），返回 {resource_id_str: {label, inactive}}"""
    result: Dict[str, Dict[str, Any]] = {}

    if resource_type == "node_type":
        # 静态类型编码，无表；编码不在受限映射内视为已删除
        for rid in resource_ids:
            if rid in NODE_TYPE_LABELS:
                result[rid] = {"label": NODE_TYPE_LABELS[rid], "inactive": False}
        return result

    int_ids: List[int] = []
    for rid in resource_ids:
        try:
            int_ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not int_ids:
        return result

    if resource_type == "model":
        from base.plugins.llm.models.model import LLMModel
        rows = await LLMModel.filter(id__in=int_ids)
        for m in rows:
            result[str(m.id)] = {
                "label": m.model_name,
                "inactive": getattr(m, "status", "active") != "active",
            }
    elif resource_type == "kb":
        from base.plugins.agent.models.rag import RAGKnowledgeBase
        rows = await RAGKnowledgeBase.filter(id__in=int_ids)
        for kb in rows:
            result[str(kb.id)] = {
                "label": kb.name,
                "inactive": getattr(kb, "status", "active") != "active",
            }
    elif resource_type == "tool":
        from base.plugins.agent.models.tool import Tool
        rows = await Tool.filter(id__in=int_ids)
        for t in rows:
            result[str(t.id)] = {
                "label": t.display_name,
                "inactive": not getattr(t, "enabled", True),
            }
    elif resource_type == "agent":
        from base.plugins.agent.models.agent import Agent
        rows = await Agent.filter(id__in=int_ids)
        for a in rows:
            result[str(a.id)] = {
                "label": a.name,
                "inactive": getattr(a, "status", "active") != "active",
            }
    return result


def _resource_status(meta: Optional[Dict[str, Any]]) -> str:
    """资源状态标注（§6.2 保留标注）：库中不存在→deleted；存在但停用→inactive"""
    if meta is None:
        return "deleted"
    return "inactive" if meta.get("inactive") else "active"


async def _enrich_org_grants(org_id: int) -> List[Dict[str, Any]]:
    """组织授权清单 enrich：复用 ResourceGrantService.list_by_subject(("org", id))

    only_valid=False 与 /admin/grants/by-subject 一致：管理端展示全部记录（含已过期）。
    注意：主体停用（org.status=disabled）时 list_by_subject 按 §6.3 返回空清单。
    """
    records = await ResourceGrantService.list_by_subject(("org", org_id), only_valid=False)

    ids_by_type: Dict[str, set] = {}
    for r in records:
        ids_by_type.setdefault(r.resource_type, set()).add(r.resource_id)
    meta_by_type: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for rtype, ids in ids_by_type.items():
        meta_by_type[rtype] = await _load_resource_meta(rtype, list(ids))

    items: List[Dict[str, Any]] = []
    for r in records:
        meta = meta_by_type.get(r.resource_type, {}).get(r.resource_id)
        items.append({
            "id": r.id,
            "owner_type": r.owner_type,
            "owner_id": r.owner_id,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "resource_name": meta["label"] if meta else r.resource_id,
            "resource_status": _resource_status(meta),
            "granted_by": getattr(r, "granted_by", ""),
            "created_at": _dt(getattr(r, "created_at", None)),
        })
    return items


# ==================== 端点 ====================

@organization_admin_router.get("", summary="组织分页列表")
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="组织名称模糊匹配"),
    status_filter: Optional[str] = Query(None, alias="status", description="状态: active/disabled"),
    admin_id: int = require_superuser(),
):
    if status_filter and status_filter not in _ORG_STATUSES:
        return fail_response(msg=f"非法组织状态: {status_filter}（支持 active/disabled）")

    from base.plugins.customer.models.customer_organization import (
        CustomerOrganization,
        CustomerOrganizationMember,
    )

    query = CustomerOrganization.all()
    if status_filter:
        query = query.filter(status=status_filter)
    keyword = (keyword or "").strip()
    if keyword:
        query = query.filter(name__icontains=keyword)

    total = await query.count()
    rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size).prefetch_related("owner_customer")
    org_ids = [o.id for o in rows]

    member_counts: Counter = Counter()
    if org_ids:
        member_counts = Counter(
            await CustomerOrganizationMember.filter(
                org_id__in=org_ids, status="active"
            ).values_list("org_id", flat=True)
        )

    items = [{
        "id": o.id,
        "name": o.name,
        "status": o.status,
        "owner_customer_id": o.owner_customer_id,
        "owner_username": getattr(o.owner_customer, "username", None),
        "member_count": member_counts.get(o.id, 0),
        "created_at": _dt(o.created_at),
    } for o in rows]
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@organization_admin_router.get("/{org_id}", summary="组织详情（成员 + 授权清单）")
async def get_organization_detail(org_id: int, admin_id: int = require_superuser()):
    from base.plugins.customer.models.customer import Customer
    from base.plugins.customer.models.customer_organization import (
        CustomerOrganization,
        CustomerOrganizationMember,
    )

    org = await CustomerOrganization.get_or_none(id=org_id)
    if not org:
        return fail_response(msg="组织不存在", status_code=status.HTTP_404_NOT_FOUND)

    owner = await Customer.get_or_none(id=org.owner_customer_id)
    memberships = await CustomerOrganizationMember.filter(
        org_id=org_id, status="active"
    ).order_by("role", "id").prefetch_related("customer")

    return success_response(data={
        "id": org.id,
        "name": org.name,
        "status": org.status,
        "created_at": _dt(org.created_at),
        "owner": {
            "customer_id": org.owner_customer_id,
            "username": getattr(owner, "username", None),
        },
        "members": [{
            "customer_id": m.customer_id,
            "username": getattr(m.customer, "username", None),
            "role": m.role,
            "joined_at": _dt(m.created_at),
        } for m in memberships],
        "grants": await _enrich_org_grants(org_id),
    })


@organization_admin_router.post("", summary="创建组织（owner 自动成为 owner 成员）")
async def create_organization(data: CreateOrganizationSchema, admin_id: int = require_superuser()):
    from base.plugins.customer.models.customer import Customer

    owner = await Customer.get_or_none(id=data.owner_customer_id)
    if not owner or not owner.is_active:
        return fail_response(msg="所有者客户不存在或已禁用")
    try:
        # 超管旁路：create_organization 无角色校验，直接以 owner_customer_id 调用（缓存失效照常触发）
        org = await CustomerOrganizationService.create_organization(data.owner_customer_id, data.name)
    except OrganizationError as exc:
        return _fail_from_error(exc)
    return success_response(
        data={"id": org.id, "name": org.name, "status": org.status}, msg="创建成功"
    )


@organization_admin_router.post("/{org_id}/members", summary="添加组织成员")
async def add_org_member(org_id: int, data: AddMemberSchema, admin_id: int = require_superuser()):
    from base.plugins.customer.models.customer import Customer
    from base.plugins.customer.models.customer_organization import CustomerOrganization

    org = await CustomerOrganization.get_or_none(id=org_id)
    if not org:
        return fail_response(msg="组织不存在", status_code=status.HTTP_404_NOT_FOUND)
    # 已是 owner：409（service 会以 owner 成员身份报 already_member，此处先行给出准确语义）
    if org.owner_customer_id == data.customer_id:
        return fail_response(msg="该客户已是组织所有者", status_code=status.HTTP_409_CONFLICT)

    try:
        # 超管旁路：显式以组织 owner 作为 operator 调用公开方法，复用同一套缓存失效钩子
        membership = await CustomerOrganizationService.add_member(
            org_id, org.owner_customer_id, data.customer_id, data.role
        )
    except OrganizationError as exc:
        return _fail_from_error(exc)

    member = await Customer.get_or_none(id=data.customer_id)
    return success_response(
        data={
            "customer_id": membership.customer_id,
            "username": getattr(member, "username", None),
            "role": membership.role,
            "joined_at": _dt(membership.created_at),
        },
        msg="添加成功",
    )


@organization_admin_router.delete("/{org_id}/members/{customer_id}", summary="移除组织成员")
async def remove_org_member(org_id: int, customer_id: int, admin_id: int = require_superuser()):
    from base.plugins.customer.models.customer_organization import CustomerOrganization

    org = await CustomerOrganization.get_or_none(id=org_id)
    if not org:
        return fail_response(msg="组织不存在", status_code=status.HTTP_404_NOT_FOUND)
    try:
        # 超管旁路：同上，operator=组织 owner，remove_member 内触发缓存失效
        await CustomerOrganizationService.remove_member(org_id, org.owner_customer_id, customer_id)
    except OrganizationError as exc:
        return _fail_from_error(exc)
    return success_response(data={"org_id": org_id, "customer_id": customer_id}, msg="移除成功")
