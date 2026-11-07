"""
组织配额数据权限：非管理员仅能访问自己关联客户所属的组织。

- 超级管理员：不受限（返回 None）
- 其他用户：通过 identity_link(linked) 找到客户主体，再解析其组织：
  - 自己作为所有者的组织
  - 以 active 成员身份加入的组织
- 未关联客户或没有任何组织时直接 403，避免用空列表掩盖越权
"""
from typing import Optional, Set

from fastapi import HTTPException, status
from loguru import logger

from base.core.users.services.user_service import UserService


def _forbidden(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _customer_models():
    from base.plugins.customer.models.customer_organization import (
        CustomerOrganization,
        CustomerOrganizationMember,
    )

    return CustomerOrganization, CustomerOrganizationMember


async def resolve_user_org_ids(user_id: int) -> Optional[Set[int]]:
    """返回可访问组织 ID 集合；超级管理员返回 None（不受限）。"""
    user = await UserService.get_by_id(user_id)
    if user is not None and user.is_superuser:
        return None

    try:
        from base.plugins.customer.models.identity_link import IdentityLink

        CustomerOrganization, CustomerOrganizationMember = _customer_models()
    except Exception as exc:  # pragma: no cover - customer 插件未启用
        logger.warning(f"[quota][org-scope] customer 插件不可用: {exc}")
        raise _forbidden("未关联客户主体，无权访问组织配额")

    link = await IdentityLink.get_or_none(user_id=user_id, status="linked")
    if link is None:
        raise _forbidden("当前账号未关联客户主体，无权访问组织配额")

    customer_id = link.customer_id
    owned = set(
        await CustomerOrganization.filter(owner_customer_id=customer_id).values_list(
            "id", flat=True
        )
    )
    joined = set(
        await CustomerOrganizationMember.filter(
            customer_id=customer_id, status="active"
        ).values_list("org_id", flat=True)
    )
    org_ids = {int(i) for i in (owned | joined)}
    if not org_ids:
        raise _forbidden("当前账号不属于任何组织，无权访问组织配额")
    return org_ids


async def ensure_org_access(user_id: int, org_id: int) -> None:
    """校验组织访问权；越权直接 403。"""
    scope = await resolve_user_org_ids(user_id)
    if scope is not None and int(org_id) not in scope:
        raise _forbidden(f"无权访问组织 {org_id}")


async def ensure_member_access(user_id: int, member_id: int) -> None:
    """校验成员是否属于当前账号可访问的组织；越权直接 403。"""
    scope = await resolve_user_org_ids(user_id)
    if scope is None:
        return
    CustomerOrganizationMember = _customer_models()[1]
    exists = await CustomerOrganizationMember.filter(
        customer_id=member_id, org_id__in=list(scope)
    ).exists()
    if not exists:
        raise _forbidden(f"无权访问成员 {member_id} 的用量流水")
