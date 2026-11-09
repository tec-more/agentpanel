"""组织目录（只读 SQL）。

组织级额度校验只需要判断「组织存在且未停用」「客户是组织活跃成员」。
L3 编排不注册客户域 ORM 模型（`CustomerOrganization.owner_customer` 外键会把
L2 的 `Customer` 模型拖进 L3 进程），因此统一走只读 SQL，不建模型、不写库。
Spec §4.2：`customer_organization` / `customer_organization_member` 只读。
"""
from typing import Any

from tortoise import Tortoise

_DB_ALIAS = "postgres"


async def organization_active(org_id: Any) -> bool:
    """组织存在且 status='active'。"""
    rows = await Tortoise.get_connection(_DB_ALIAS).execute_query_dict(
        "SELECT 1 AS ok FROM customer_organization "
        "WHERE id = $1 AND status = 'active' LIMIT 1",
        [int(org_id)],
    )
    return bool(rows)


async def member_active(org_id: Any, customer_id: Any) -> bool:
    """客户是该组织的活跃成员。"""
    rows = await Tortoise.get_connection(_DB_ALIAS).execute_query_dict(
        "SELECT 1 AS ok FROM customer_organization_member "
        "WHERE org_id = $1 AND customer_id = $2 AND status = 'active' LIMIT 1",
        [int(org_id), int(customer_id)],
    )
    return bool(rows)


__all__ = ["member_active", "organization_active"]
