"""
M11 客户组织服务（Q-H）与 HITL 审批人解析

溯源：
- docs/arch/02-系统上下文与领域模型.md §2.1 M11、§4.2 customer_organization(_member)
- docs/arch/04-核心流程与接口契约.md §6 resolve_assignee(mode, owner) -> principal
- PRD §5.9 HITL 审批人仅限本人或同组织成员

边界禁区（C-23）：仅客户域；不引入组织级配额；不复用后台 Department。
"""
from typing import List, Optional

from base.common.authz.constants import OwnerType
from base.common.authz.context import OwnerContext
from base.plugins.customer.models.customer_organization import (
    CustomerOrganization,
    CustomerOrganizationMember,
)

# 成员角色
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
VALID_ROLES = (ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER)

# 审批人解析模式（PRD §5.9 assignee_mode）
MODE_SELF = "self"
MODE_ORG_ROLE = "org_role"
MODE_SPECIFIC_USER = "specific_user"


class OrganizationError(Exception):
    """客户组织业务异常"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CustomerOrganizationService:
    """客户组织 CRUD 与成员管理（owner/admin/member）"""

    @staticmethod
    async def _get_membership(org_id: int, customer_id: int) -> Optional[CustomerOrganizationMember]:
        return await CustomerOrganizationMember.get_or_none(
            org_id=org_id, customer_id=customer_id, status="active"
        )

    @classmethod
    async def _require_role(cls, org_id: int, customer_id: int, roles: tuple) -> CustomerOrganizationMember:
        membership = await cls._get_membership(org_id, customer_id)
        if not membership or membership.role not in roles:
            raise OrganizationError("forbidden", "无权限执行该操作（需要组织 " + "/".join(roles) + " 角色）")
        return membership

    # ---------- 组织 CRUD ----------

    @classmethod
    async def create_organization(cls, owner_customer_id: int, name: str) -> CustomerOrganization:
        """创建组织；创建者自动成为 owner 成员"""
        if not name or not name.strip():
            raise OrganizationError("invalid_name", "组织名称不能为空")
        org = await CustomerOrganization.create(
            name=name.strip(), owner_customer_id=owner_customer_id
        )
        await CustomerOrganizationMember.create(
            org_id=org.id, customer_id=owner_customer_id, role=ROLE_OWNER
        )
        # §6.1：组织授权缓存失效（新组织 owner 获得成员关系）
        from base.common.authz.service import invalidate_customer_org_cache
        await invalidate_customer_org_cache(owner_customer_id)
        return org

    @classmethod
    async def list_my_organizations(cls, customer_id: int) -> List[dict]:
        """我加入的组织列表（含我的角色）"""
        memberships = await CustomerOrganizationMember.filter(
            customer_id=customer_id, status="active"
        ).prefetch_related("org")
        return [
            {
                "org_id": m.org_id,
                "name": m.org.name,
                "org_status": m.org.status,
                "my_role": m.role,
            }
            for m in memberships
        ]

    @classmethod
    async def get_organization(cls, org_id: int, customer_id: int) -> CustomerOrganization:
        """组织详情（仅成员可见）"""
        await cls._require_role(org_id, customer_id, VALID_ROLES)
        org = await CustomerOrganization.get_or_none(id=org_id)
        if not org:
            raise OrganizationError("not_found", "组织不存在")
        return org

    @classmethod
    async def update_organization(
        cls, org_id: int, operator_customer_id: int, *, name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> CustomerOrganization:
        """更新组织（owner/admin）"""
        await cls._require_role(org_id, operator_customer_id, (ROLE_OWNER, ROLE_ADMIN))
        org = await CustomerOrganization.get_or_none(id=org_id)
        if not org:
            raise OrganizationError("not_found", "组织不存在")
        if name is not None:
            if not name.strip():
                raise OrganizationError("invalid_name", "组织名称不能为空")
            org.name = name.strip()
        if status is not None:
            if status not in ("active", "disabled"):
                raise OrganizationError("invalid_status", "非法组织状态")
            org.status = status
        await org.save()
        return org

    # ---------- 成员管理 ----------

    @classmethod
    async def list_members(cls, org_id: int, customer_id: int) -> List[dict]:
        """成员列表（成员可见）"""
        await cls._require_role(org_id, customer_id, VALID_ROLES)
        members = await CustomerOrganizationMember.filter(
            org_id=org_id, status="active"
        ).prefetch_related("customer")
        return [
            {
                "customer_id": m.customer_id,
                "username": m.customer.username,
                "nickname": m.customer.nickname,
                "role": m.role,
            }
            for m in members
        ]

    @classmethod
    async def add_member(
        cls, org_id: int, operator_customer_id: int, member_customer_id: int, role: str = ROLE_MEMBER
    ) -> CustomerOrganizationMember:
        """添加成员（owner/admin；不可添加 owner 角色）"""
        await cls._require_role(org_id, operator_customer_id, (ROLE_OWNER, ROLE_ADMIN))
        if role not in (ROLE_ADMIN, ROLE_MEMBER):
            raise OrganizationError("invalid_role", "仅可添加 admin/member 角色成员")

        org = await CustomerOrganization.get_or_none(id=org_id)
        if not org or org.status != "active":
            raise OrganizationError("org_unavailable", "组织不存在或已停用")

        from base.plugins.customer.models.customer import Customer
        member_customer = await Customer.get_or_none(id=member_customer_id)
        if not member_customer or not member_customer.is_active:
            raise OrganizationError("member_unavailable", "目标客户不存在或已禁用")

        existing = await CustomerOrganizationMember.get_or_none(
            org_id=org_id, customer_id=member_customer_id
        )
        # §6.1：成员关系变化 → 失效该 customer 的组织授权缓存
        from base.common.authz.service import invalidate_customer_org_cache
        if existing:
            if existing.status == "active":
                raise OrganizationError("already_member", "该客户已是组织成员")
            existing.status = "active"
            existing.role = role
            await existing.save()
            await invalidate_customer_org_cache(member_customer_id)
            return existing

        membership = await CustomerOrganizationMember.create(
            org_id=org_id, customer_id=member_customer_id, role=role
        )
        await invalidate_customer_org_cache(member_customer_id)
        return membership

    @classmethod
    async def remove_member(
        cls, org_id: int, operator_customer_id: int, member_customer_id: int
    ) -> None:
        """移除成员（owner/admin；不可移除 owner）"""
        await cls._require_role(org_id, operator_customer_id, (ROLE_OWNER, ROLE_ADMIN))
        membership = await cls._get_membership(org_id, member_customer_id)
        if not membership:
            raise OrganizationError("not_member", "目标客户不是组织成员")
        if membership.role == ROLE_OWNER:
            raise OrganizationError("cannot_remove_owner", "不可移除组织所有者")
        membership.status = "removed"
        await membership.save()
        # §6.1：成员被移除 → 失效组织授权缓存（自动失去组织资源权限）
        from base.common.authz.service import invalidate_customer_org_cache
        await invalidate_customer_org_cache(member_customer_id)

    @classmethod
    async def update_member_role(
        cls, org_id: int, operator_customer_id: int, member_customer_id: int, role: str
    ) -> CustomerOrganizationMember:
        """变更成员角色（仅 owner；owner 角色本身不可被变更）"""
        await cls._require_role(org_id, operator_customer_id, (ROLE_OWNER,))
        if role not in (ROLE_ADMIN, ROLE_MEMBER):
            raise OrganizationError("invalid_role", "仅可设置为 admin/member 角色")
        membership = await cls._get_membership(org_id, member_customer_id)
        if not membership:
            raise OrganizationError("not_member", "目标客户不是组织成员")
        if membership.role == ROLE_OWNER:
            raise OrganizationError("cannot_change_owner", "不可变更组织所有者角色")
        membership.role = role
        await membership.save()
        return membership

    @classmethod
    async def list_org_member_customer_ids(cls, org_id: int) -> List[int]:
        """组织内全部活跃成员客户 ID（HITL 范围解析用）"""
        return await CustomerOrganizationMember.filter(
            org_id=org_id, status="active"
        ).values_list("customer_id", flat=True)


async def resolve_assignee(
    mode: str,
    owner: OwnerContext,
    assignee_refs: Optional[List[str]] = None,
) -> dict:
    """
    HITL 审批人解析（docs/arch/04 §6 契约：resolve_assignee(mode, owner) -> principal）

    P0 范围：
    - 客户域（cus）：仅支持 self
    - 后台域（usr）：self；specific_user 按 data_scope 可见属主集合校验
    - org_role（组织成员解析）：接口已定义，留给后续迭代
    """
    if mode == MODE_SELF:
        return {
            "principal_type": owner.owner_type,
            "principal_id": owner.owner_id,
            "mode": MODE_SELF,
        }

    if owner.owner_type == OwnerType.CUS.value:
        # P0 客户域仅支持 self（04 §7 N4-5）
        raise OrganizationError(
            "unsupported_mode",
            f"客户域 P0 仅支持 self 审批人模式，暂不支持 {mode}",
        )

    # usr 域
    if mode == MODE_SPECIFIC_USER:
        refs = [int(r) for r in (assignee_refs or []) if str(r).isdigit()]
        if not refs:
            raise OrganizationError("missing_assignee", "specific_user 模式必须指定审批人")
        visible = owner.visible_user_ids
        if visible is not None:
            invalid = [r for r in refs if r not in visible]
            if invalid:
                raise OrganizationError(
                    "assignee_out_of_scope",
                    f"审批人超出数据权限范围: {invalid}",
                )
        return {
            "principal_type": OwnerType.USR.value,
            "principal_id": refs[0],
            "mode": MODE_SPECIFIC_USER,
            "candidates": refs,
        }

    if mode == MODE_ORG_ROLE:
        # 组织成员解析留给后续迭代（接口先行定义）
        raise NotImplementedError("org_role 审批人模式将在后续迭代提供")

    raise OrganizationError("unsupported_mode", f"不支持的审批人模式: {mode}")
