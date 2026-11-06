"""
M8 数据范围解析（resolve_scope）

溯源：docs/arch/04-核心流程与接口契约.md §6 内部接口
    M3→M8: resolve_scope(owner) -> {data_scope, org_ids}

语义（PRD §7.1 强制规则 4）：
- cus：客户主体 P0 仅 self（客户组织 org_ids 由 T3/M11 扩展，本任务不实现）
- usr：叠加现有 RBAC data_scope（base/core/users/models/rbac.py），
  org_ids 返回该范围覆盖的部门 ID 集合：
    all       → []（无需部门过滤）
    dept      → [本部门]
    dept_tree → [本部门及全部下级部门]
    custom    → 角色自定义部门集合
    self      → []
"""
from typing import Dict, List, Optional

from .constants import OwnerType, DataScope
from .context import OwnerContext


async def resolve_scope(owner: OwnerContext) -> Dict:
    """
    解析主体数据范围

    Returns:
        {"data_scope": str, "org_ids": List[int], "is_superuser": bool}
        - data_scope: all/dept_tree/dept/custom/self（cus 恒为 self）
        - org_ids: usr 为部门 ID 集合；cus 为组织 ID 集合（P0 为空，T3 扩展）
    """
    if owner.owner_type == OwnerType.CUS.value:
        # 客户域：P0 仅本人；组织成员关系解析属 T3（M11 身份与组织）范围
        return {"data_scope": DataScope.SELF.value, "org_ids": [], "is_superuser": False}

    return await _resolve_user_scope(owner.owner_id)


async def _resolve_user_scope(user_id: int) -> Dict:
    """usr 数据范围：复用现有 RBAC DataPermissionService 语义（多角色取最大范围）"""
    from base.core.users.services.rbac_service import DataPermissionService

    scope_info = await DataPermissionService.get_user_data_scope(user_id)
    scope = scope_info.get("scope", DataScope.SELF.value)
    user_dept_id = scope_info.get("user_dept_id")
    is_superuser = scope == DataScope.ALL.value

    org_ids: List[int] = []
    if scope == DataScope.DEPT.value:
        org_ids = [user_dept_id] if user_dept_id else []
    elif scope == DataScope.DEPT_TREE.value:
        if user_dept_id:
            org_ids = await DataPermissionService.get_dept_tree_ids_async(user_dept_id)
    elif scope == DataScope.CUSTOM.value:
        org_ids = list(scope_info.get("dept_ids") or [])
    # all/self 无需部门集合

    return {"data_scope": scope, "org_ids": org_ids, "is_superuser": is_superuser}


async def resolve_scope_user_ids(owner: OwnerContext) -> Optional[List[int]]:
    """
    将 usr 数据范围解析为可见的属主用户 ID 集合（L1 一次性解析，L2 过滤消费）

    Returns:
        None       → all 档，不限制 owner_id
        [user_ids] → self 档为 [本人]；dept/dept_tree/custom 档为范围内部门成员 + 本人
    部门解析异常或无部门时安全收缩为仅本人。
    """
    if owner.data_scope == DataScope.ALL.value:
        return None
    if owner.data_scope in (
        DataScope.DEPT.value,
        DataScope.DEPT_TREE.value,
        DataScope.CUSTOM.value,
    ) and owner.org_ids:
        from base.core.users.models.users import User

        user_ids = await User.filter(dept_id__in=owner.org_ids).values_list("id", flat=True)
        ids = [int(uid) for uid in user_ids]
        if owner.owner_id not in ids:
            ids.append(owner.owner_id)  # 本人数据始终可见
        return ids
    return [owner.owner_id]
