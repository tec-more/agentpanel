"""
M8 资源授权服务（ResourceGrant）

溯源：
- docs/arch/04 §6 内部接口：M3→M8 check_resource_access(owner, resource_type, resource_id) -> bool
- docs/用户侧智能体设计流PRD.md §7.2 授权矩阵（模型/知识库/工具/子Agent/节点类型）
- 模型定义见 models/resource_grant.py（T1 交付，四元组唯一约束）

默认策略（PRD §7.2）：模型仅基础可用、工具/子 Agent 默认关闭、公共知识库需显式授权。
因此本服务只做显式授权判定（存在 allow 且未过期即放行），不做任何隐式放行。
"""
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Set, Tuple, Union

from .context import OwnerContext
from .models.resource_grant import ResourceGrant

# check_resource_access 接受 OwnerContext 或 (owner_type, owner_id) 二元组
OwnerLike = Union[OwnerContext, Tuple[str, int]]

# 组织成员关系缓存（§6.1 性能对策：check 热路径避免每次查库）
_ORG_IDS_CACHE_PREFIX = "authz:org_ids:"
_ORG_IDS_CACHE_TTL = 300  # 秒；成员变动由 organization_service 主动失效，TTL 仅兜底


def _split_owner(owner: OwnerLike) -> Tuple[str, int]:
    if isinstance(owner, OwnerContext):
        return owner.owner_type, owner.owner_id
    return owner[0], owner[1]


def _is_valid_grant(record: ResourceGrant) -> bool:
    """授权记录有效性：effect=allow 且未过期（时区安全：naive 按本地时间、aware 按 UTC 比较）"""
    if record.effect != "allow":
        return False
    if record.expires_at is None:
        return True
    expires = record.expires_at
    if expires.tzinfo is not None:
        return expires > datetime.now(timezone.utc)
    return expires > datetime.now()


async def is_subject_active(owner_type: str, owner_id: int) -> bool:
    """
    主体有效性校验（资源授权管理 PRD §6.3）：不存在/已禁用主体不放行，恢复后自动恢复。

    分层说明：authz 属 common 层，主体模型在 plugins/core 层，按项目惯例
    （同 agent 插件 u_resource_router._load_metadata）函数内延迟 import，避免模块级反向依赖。
    """
    if owner_type == "cus":
        from base.plugins.customer.models.customer import Customer
        customer = await Customer.get_or_none(id=owner_id)
        return bool(customer and customer.is_active)
    if owner_type == "usr":
        from base.core.users.models.users import User
        user = await User.get_or_none(id=owner_id)
        return bool(user and getattr(user, "is_active", True))
    if owner_type == "org":
        from base.plugins.customer.models.customer_organization import CustomerOrganization
        org = await CustomerOrganization.get_or_none(id=owner_id)
        return bool(org and org.status == "active")
    return False


async def _customer_org_ids(customer_id: int) -> List[int]:
    """
    customer 所属有效组织 id 列表（status=active 成员关系 + 组织本身 active）。

    缓存读穿：Redis 短 TTL（BUG-OPS-001 修复后用法：先 get_instance 再判 is_enabled）；
    失效由 CustomerOrganizationService.add_member/remove_member/create_organization 挂钩。
    """
    cache_key = f"{_ORG_IDS_CACHE_PREFIX}{customer_id}"
    try:
        from base.common.cache import RedisCache
        cache = await RedisCache.get_instance()
        if cache and cache.is_enabled():
            cached = await cache.get(cache_key)
            if cached is not None:
                return [int(x) for x in cached.split(",") if x]
    except Exception:
        pass  # 缓存不可用降级为直查库，不阻断判定

    from base.plugins.customer.models.customer_organization import (
        CustomerOrganization,
        CustomerOrganizationMember,
    )
    memberships = await CustomerOrganizationMember.filter(
        customer_id=customer_id, status="active"
    ).values_list("org_id", flat=True)
    if not memberships:
        org_ids: List[int] = []
    else:
        org_ids = await CustomerOrganization.filter(
            id__in=list(memberships), status="active"
        ).values_list("id", flat=True)
        org_ids = list(org_ids)

    try:
        from base.common.cache import RedisCache
        cache = await RedisCache.get_instance()
        if cache and cache.is_enabled():
            await cache.set(cache_key, ",".join(str(i) for i in org_ids), expire=_ORG_IDS_CACHE_TTL)
    except Exception:
        pass
    return org_ids


async def invalidate_customer_org_cache(customer_id: int) -> None:
    """组织成员变动时失效 customer 的组织缓存（供 customer 插件 organization_service 调用）"""
    try:
        from base.common.cache import RedisCache
        cache = await RedisCache.get_instance()
        if cache and cache.is_enabled():
            await cache.delete(f"{_ORG_IDS_CACHE_PREFIX}{customer_id}")
    except Exception:
        pass  # 失效失败不阻断业务，TTL 兜底


async def _has_valid_grant(
    owner_type: str,
    owner_ids: Union[int, List[int]],
    resource_type: str,
    resource_id: str,
) -> bool:
    """单 id / id 列表的有效授权存在性判定（四元组唯一，过期判定 Python 侧时区安全）"""
    query = ResourceGrant.filter(
        owner_type=owner_type,
        resource_type=resource_type,
        resource_id=str(resource_id),
        effect="allow",
    )
    if isinstance(owner_ids, list):
        if not owner_ids:
            return False
        query = query.filter(owner_id__in=owner_ids)
    else:
        query = query.filter(owner_id=owner_ids)
    records = await query
    return any(_is_valid_grant(r) for r in records)


class ResourceGrantService:
    """ResourceGrant 内部服务接口（T5/T6/T11 消费，禁止业务层直接拼装授权判断）"""

    @staticmethod
    async def check_resource_access(
        owner: OwnerLike,
        resource_type: str,
        resource_id: Union[str, int],
    ) -> bool:
        """
        判定主体是否已获某资源授权

        Args:
            owner: OwnerContext 或 (owner_type, owner_id)
            resource_type: model/kb/tool/agent/node_type
            resource_id: 资源标识（数值 ID 字符串形式或类型编码）

        Returns:
            存在 effect=allow 且未过期的授权记录 → True
        """
        owner_type, owner_id = _split_owner(owner)
        # §6.3：主体有效性校验（不存在/已禁用不放行，恢复后自动恢复）
        if not await is_subject_active(owner_type, owner_id):
            return False
        # 1. 主体自身授权（四元组唯一，至多一行）
        if await _has_valid_grant(owner_type, owner_id, resource_type, str(resource_id)):
            return True
        # 2. §6.1：customer 追加所属组织授权维度（成员变动自动生效/失效）
        if owner_type == "cus":
            org_ids = await _customer_org_ids(owner_id)
            if org_ids and await _has_valid_grant("org", org_ids, resource_type, str(resource_id)):
                return True
        return False

    @staticmethod
    async def check_many(
        owner: OwnerLike,
        resource_type: str,
        resource_ids: Sequence[Union[str, int]],
    ) -> Set[str]:
        """
        批量判定（资源选择器/保存时引用校验用）

        Returns:
            已授权 resource_id 集合（字符串形式）
        """
        if not resource_ids:
            return set()
        owner_type, owner_id = _split_owner(owner)
        # §6.3：主体有效性校验（与 check_resource_access 语义一致）
        if not await is_subject_active(owner_type, owner_id):
            return set()
        str_ids = [str(r) for r in resource_ids]
        rows = await ResourceGrant.filter(
            owner_type=owner_type,
            owner_id=owner_id,
            resource_type=resource_type,
            resource_id__in=str_ids,
            effect="allow",
        )
        granted = {r.resource_id for r in rows if _is_valid_grant(r)}
        # §6.1：customer 追加所属组织授权（仅补查未命中部分，减少返回行数）
        if owner_type == "cus":
            missing = [rid for rid in str_ids if rid not in granted]
            if missing:
                org_ids = await _customer_org_ids(owner_id)
                if org_ids:
                    org_rows = await ResourceGrant.filter(
                        owner_type="org",
                        owner_id__in=org_ids,
                        resource_type=resource_type,
                        resource_id__in=missing,
                        effect="allow",
                    )
                    granted |= {r.resource_id for r in org_rows if _is_valid_grant(r)}
        return granted

    @staticmethod
    async def grant(
        owner: OwnerLike,
        resource_type: str,
        resource_id: Union[str, int],
        granted_by: str = "admin",
        expires_at: Optional[datetime] = None,
    ) -> ResourceGrant:
        """
        授权（幂等：四元组唯一约束，重复授权返回既有记录并刷新过期时间）

        R-06 openGauss 红线：使用 get_or_create，不使用 ON CONFLICT。
        """
        owner_type, owner_id = _split_owner(owner)
        record, created = await ResourceGrant.get_or_create(
            owner_type=owner_type,
            owner_id=owner_id,
            resource_type=resource_type,
            resource_id=str(resource_id),
            defaults={
                "effect": "allow",
                "granted_by": granted_by,
                "expires_at": expires_at,
            },
        )
        if not created:
            # 幂等重放：仅刷新元信息，不新增行
            changed = False
            if record.effect != "allow":
                record.effect = "allow"
                changed = True
            if expires_at is not None and record.expires_at != expires_at:
                record.expires_at = expires_at
                changed = True
            if changed:
                await record.save()
        return record

    @staticmethod
    async def revoke(
        owner: OwnerLike,
        resource_type: str,
        resource_id: Union[str, int],
    ) -> int:
        """
        撤销授权

        Returns:
            删除的记录数（0 表示本不存在，幂等）
        """
        owner_type, owner_id = _split_owner(owner)
        # D3 修复：逐条实例删除以触发审计插件（QuerySet.delete() 绕过实例钩子，撤销无审计留痕）
        records = await ResourceGrant.filter(
            owner_type=owner_type,
            owner_id=owner_id,
            resource_type=resource_type,
            resource_id=str(resource_id),
        ).all()
        for record in records:
            await record.delete()
        return len(records)

    @staticmethod
    async def list_by_subject(
        owner: OwnerLike,
        resource_type: Optional[str] = None,
        only_valid: bool = True,
    ) -> List[ResourceGrant]:
        """按主体查询授权清单（资源选择器"已授权"视图用）

        §6.1：cus 主体追加合并所属组织授权（org 记录原样返回，owner_type="org"）；
        同一 (resource_type, resource_id) 下主体自身记录优先，组织授权去重后补入。
        """
        owner_type, owner_id = _split_owner(owner)
        # D1 修复：视图层与判定语义一致——禁用/删除主体返回空清单（§6.3）
        if not await is_subject_active(owner_type, owner_id):
            return []
        query = ResourceGrant.filter(owner_type=owner_type, owner_id=owner_id)
        if resource_type:
            query = query.filter(resource_type=resource_type)
        records = await query.order_by("resource_type", "resource_id")
        # cus 主体合并组织授权（选择器视图与运行时判定语义一致）
        if owner_type == "cus":
            org_ids = await _customer_org_ids(owner_id)
            if org_ids:
                org_query = ResourceGrant.filter(owner_type="org", owner_id__in=org_ids)
                if resource_type:
                    org_query = org_query.filter(resource_type=resource_type)
                org_records = await org_query.order_by("resource_type", "resource_id")
                seen = {(r.resource_type, r.resource_id) for r in records}
                records = records + [
                    r for r in org_records if (r.resource_type, r.resource_id) not in seen
                ]
        if only_valid:
            records = [r for r in records if _is_valid_grant(r)]
        return records

    @staticmethod
    async def list_by_resource(
        resource_type: str,
        resource_id: Union[str, int],
    ) -> List[ResourceGrant]:
        """按资源反查被授权主体（管理侧授权管理/审计用）"""
        return await ResourceGrant.filter(
            resource_type=resource_type,
            resource_id=str(resource_id),
        ).order_by("owner_type", "owner_id")


async def check_resource_access(
    owner: OwnerLike,
    resource_type: str,
    resource_id: Union[str, int],
) -> bool:
    """模块级便捷入口（04-§6 契约签名）"""
    return await ResourceGrantService.check_resource_access(owner, resource_type, resource_id)
