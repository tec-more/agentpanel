"""
L2 路由层：声明式归属过滤

溯源：
- docs/arch/05 §2.1 L2：归属过滤注入所有 ORM 查询（强制，非各接口手写）；不匹配 → 404
- R-01：所有 ORM 查询必须经归属过滤中间件，禁止手写绕过；越权返回 404
- PRD §7.1 强制规则 1/2/3/4：
  1) 列表/详情/编辑/执行/删除接口必须带归属过滤；鉴权失败统一 404（不暴露存在性）
  2) 跨归属访问一律拒绝并记录审计
  3) 公共资源只读；修改需复制为私有副本
  4) usr 除归属过滤外必须叠加角色 data_scope，两者同时满足才可访问

设计：usr 数据范围的用户集合在 L1（AuthzContextMiddleware / require_owner）一次性解析
进 OwnerContext.visible_user_ids，本模块过滤构建保持纯同步，QuerySet 可直接链式追加
业务条件（状态/关键字等），天然声明式。

接入方式（T5/T6 声明式消费，禁止手写 owner 条件）：
    rows = await owned_queryset(Workflow).filter(status="active")     # 列表：当前主体可见集合
    wf = await get_owned_or_404(Workflow, wf_id)                      # 详情/写操作：单条强校验
    wf = await get_owned_or_404(Workflow, wf_id, include_public=True) # 公开只读可读

适用模型：带 owner_type/owner_id 字段的归属资源模型（T1 已扩展）；
visibility 字段仅部分模型（workflow/agent/rag_knowledge_base）具备，
include_public=True 时自动检测模型是否具备该字段。
"""
from typing import Optional, Type, Union

from fastapi import HTTPException, status
from tortoise.expressions import Q
from tortoise.models import Model
from tortoise.queryset import QuerySet

from .audit import record_violation
from .constants import DataScope, OwnerType
from .context import OwnerContext, get_current_owner

# PRD §7.1 可见性：公开只读/模板（读操作可跨归属，写操作严格私有）
PUBLIC_VISIBILITIES = ("public", "template")


class OwnedResourceNotFound(HTTPException):
    """
    归属不可见 404（404xx 段位，docs/arch/04 §2.3）

    对"不存在"与"越权"返回完全相同的 404 响应体（不暴露存在性，PRD §7.1 规则 1）。
    """

    def __init__(self, detail: str = "资源不存在"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _require_context_owner(owner: Optional[OwnerContext]) -> OwnerContext:
    """取上下文主体；未认证 → 401（L1 语义）"""
    if owner is not None:
        return owner
    ctx = get_current_owner()
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return ctx


def _model_has_visibility(model: Type[Model]) -> bool:
    return "visibility" in model._meta.fields_map


def build_owner_filter(
    owner: OwnerContext,
    *,
    include_public: bool = False,
    for_write: bool = False,
    model: Optional[Type[Model]] = None,
) -> Q:
    """
    构建当前主体的归属过滤条件（Q 对象，供组合查询，纯同步）

    - cus：Q(owner_type=cus, owner_id=本人)
    - usr：Q(owner_type=usr) 叠加 data_scope：
        all                   → 不限制 owner_id
        self                  → owner_id=本人
        dept/dept_tree/custom → owner_id ∈ visible_user_ids（L1 已解析；未解析安全收缩为本人）
    - include_public（仅读且模型具备 visibility）：附加 OR visibility ∈ (public, template)
    - for_write：严格归属（公开只读不可写，PRD §7.1 规则 3）
    """
    if owner.owner_type == OwnerType.CUS.value:
        base = Q(owner_type=OwnerType.CUS.value, owner_id=owner.owner_id)
    else:
        if owner.data_scope == DataScope.ALL.value:
            base = Q(owner_type=OwnerType.USR.value)
        elif owner.visible_user_ids is not None:
            base = Q(owner_type=OwnerType.USR.value, owner_id__in=owner.visible_user_ids)
        else:
            # self 档或未完成 L1 解析：安全收缩为仅本人
            base = Q(owner_type=OwnerType.USR.value, owner_id=owner.owner_id)

    if include_public and not for_write and model is not None and _model_has_visibility(model):
        base = base | Q(visibility__in=PUBLIC_VISIBILITIES)
    return base


def owned_queryset(
    model: Type[Model],
    owner: Optional[OwnerContext] = None,
    *,
    include_public: bool = False,
    for_write: bool = False,
) -> QuerySet:
    """
    返回携带强制归属过滤的 QuerySet（L2 声明式接入点，可继续链式 filter）

    Args:
        model: 归属资源模型（必须具备 owner_type/owner_id 字段）
        owner: 主体上下文，默认取当前请求上下文（中间件注入）
        include_public: 读场景是否并入公开只读资源（visibility public/template）
        for_write: 写场景（禁用公开并入）
    """
    owner = _require_context_owner(owner)
    if "owner_type" not in model._meta.fields_map or "owner_id" not in model._meta.fields_map:
        raise TypeError(
            f"{model.__name__} 不具备 owner_type/owner_id 字段，无法应用归属过滤"
        )
    q = build_owner_filter(
        owner, include_public=include_public, for_write=for_write, model=model
    )
    return model.all().filter(q)


def is_accessible(
    obj: Model,
    owner: OwnerContext,
    *,
    include_public: bool = False,
    for_write: bool = False,
) -> bool:
    """对象级归属判定（get_owned_or_404 与 L3 复核共用，纯同步）"""
    obj_owner_type = getattr(obj, "owner_type", None)
    obj_owner_id = getattr(obj, "owner_id", None)

    # 本人资源恒可访问
    if obj_owner_type == owner.owner_type and obj_owner_id is not None \
            and int(obj_owner_id) == owner.owner_id:
        return True

    # 公开只读资源：读操作跨归属可见（PRD §7.1 规则 3）；写操作不可
    if not for_write and include_public:
        visibility = getattr(obj, "visibility", None)
        if visibility in PUBLIC_VISIBILITIES:
            return True

    # usr 叠加 data_scope：仅对 usr 域资源生效（PRD §7.1 规则 4）
    if owner.owner_type == OwnerType.USR.value and obj_owner_type == OwnerType.USR.value:
        if owner.data_scope == DataScope.ALL.value:
            return True
        if obj_owner_id is None:
            return False
        if owner.visible_user_ids is not None:
            return int(obj_owner_id) in owner.visible_user_ids
        # self 档/未解析：仅本人（上方已判定）
    return False


async def get_owned_or_404(
    model: Type[Model],
    pk: Union[int, str],
    owner: Optional[OwnerContext] = None,
    *,
    include_public: bool = False,
    for_write: bool = False,
) -> Model:
    """
    单条归属强校验：不存在与越权统一 404（不暴露存在性）

    流程（F8）：
    1. 不带归属条件按主键查询
    2. 不存在 → 404
    3. 存在但归属/数据范围不匹配 → 记录越权审计（warn + 计数限流，F8）→ 404
    4. 匹配 → 返回实例
    """
    owner = _require_context_owner(owner)
    obj = await model.filter(pk=pk).first()
    if obj is None:
        raise OwnedResourceNotFound()

    if not is_accessible(obj, owner, include_public=include_public, for_write=for_write):
        # 真实越权（资源存在但归属不匹配）：审计 warn + F8 计数限流
        await record_violation(
            owner.identity,
            path=owner.request_path or "-",
            method=owner.request_method or "-",
            resource_hint=f"{model._meta.db_table}:{pk}",
        )
        raise OwnedResourceNotFound()
    return obj
