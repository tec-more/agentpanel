from typing import Optional
from base.common.permissions import get_user_permissions_cached, get_user_data_scope_cached


async def get_crm_data_filter(user_id: int) -> dict:
    user_perms = await get_user_permissions_cached(user_id)
    if "*" in user_perms:
        return {}
    data_scope = await get_user_data_scope_cached(user_id)
    scope_type = data_scope.get("scope_type", "self")
    if scope_type == "all":
        return {}
    if scope_type in ("dept", "dept_and_sub"):
        dept_user_ids = data_scope.get("user_ids", [])
        if dept_user_ids:
            return {"assigned_to__in": dept_user_ids}
        return {"assigned_to": user_id}
    return {"assigned_to": user_id}