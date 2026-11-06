"""
角色权限管理API
"""
from fastapi import APIRouter, Depends, status, Query
from typing import Optional, List

from base.core.users.schemas.rbac import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleWithPermissions,
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
    UserRoleAssign,
    RolePermissionAssign,
    RolePermissionGroupAssign,
    PermissionGroupCreate,
    PermissionGroupUpdate,
    PermissionGroupResponse,
    PermissionGroupWithPermissions,
    PermissionGroupPermissionAssign,
)
from base.core.users.services.rbac_service import (
    RoleService,
    PermissionService,
    PermissionGroupService,
)
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.permissions import (
    require_permission,
    require_any_permission,
    clear_role_users_cache,
    clear_user_permission_cache,
)
from base.common.response import SuccessResponse, ErrorResponse

router = APIRouter(prefix="/v1/rbac", tags=["角色权限管理"])


# ==================== 角色管理 ==================== #

@router.get("/roles/list", summary="获取角色列表")
async def get_role_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量"),
        name: Optional[str] = Query(None, description="角色名称(模糊搜索)"),
        is_active: Optional[bool] = Query(None, description="是否激活"),
        user_id: int = require_permission("role:list")
):
    """获取角色列表"""
    roles, total = await RoleService.get_role_list(
        page=page,
        page_size=page_size,
        name=name,
        is_active=is_active,
    )

    role_list = []
    for role in roles:
        role_dict = await role.to_dict()
        role_list.append(role_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": role_list
    }

    return SuccessResponse(data=response_data)


@router.get("/roles/tree", summary="获取角色树形结构")
async def get_role_tree(user_id: int = require_permission("role:list")):
    """获取角色树形结构（用于角色继承选择）"""
    tree = await RoleService.get_role_tree()
    return SuccessResponse(data=tree)


@router.get("/roles/{role_id}", summary="获取角色详情")
async def get_role_detail(
        role_id: int,
        user_id: int = require_permission("role:list")
):
    """获取角色详情(包含权限列表)"""
    role = await RoleService.get_by_id(role_id)
    if not role:
        return ErrorResponse(msg="角色不存在", status_code=status.HTTP_404_NOT_FOUND)

    role_dict = await role.to_dict(include_permissions=True, include_groups=True)
    return SuccessResponse(data=role_dict)


@router.post("/roles", summary="创建角色")
async def create_role(
        role_data: RoleCreate,
        user_id: int = require_permission("role:create")
):
    """创建角色"""
    # 检查角色编码是否存在
    if await RoleService.check_code_exists(role_data.code):
        return ErrorResponse(msg="角色编码已存在", status_code=status.HTTP_400_BAD_REQUEST)

    # 检查父角色是否存在
    if role_data.parent_id:
        parent_role = await RoleService.get_by_id(role_data.parent_id)
        if not parent_role:
            return ErrorResponse(msg="父角色不存在", status_code=status.HTTP_400_BAD_REQUEST)

    # 创建角色
    role = await RoleService.create_role(role_data)
    role_dict = await role.to_dict()

    return SuccessResponse(data=role_dict, msg="创建成功")


@router.put("/roles/{role_id}", summary="更新角色")
async def update_role(
        role_id: int,
        role_data: RoleUpdate,
        user_id: int = require_permission("role:update")
):
    """更新角色"""
    role = await RoleService.update_role(role_id, role_data)
    if not role:
        return ErrorResponse(msg="角色不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 清除该角色下所有用户的权限缓存
    await clear_role_users_cache(role_id)

    role_dict = await role.to_dict()
    return SuccessResponse(data=role_dict, msg="更新成功")


@router.delete("/roles/{role_id}", summary="删除角色")
async def delete_role(
        role_id: int,
        user_id: int = require_permission("role:delete")
):
    """删除角色"""
    # 清除该角色下所有用户的权限缓存
    await clear_role_users_cache(role_id)

    success = await RoleService.delete_role(role_id)
    if not success:
        return ErrorResponse(msg="角色不存在或存在子角色无法删除", status_code=status.HTTP_400_BAD_REQUEST)

    return SuccessResponse(msg="删除成功")


@router.post("/roles/{role_id}/permissions", summary="为角色分配权限")
async def assign_permissions(
        role_id: int,
        assign_data: RolePermissionAssign,
        user_id: int = require_permission("role:update")
):
    """为角色分配权限"""
    success = await RoleService.assign_permissions_to_role(role_id, assign_data.permission_ids)
    if not success:
        return ErrorResponse(msg="角色不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 清除该角色下所有用户的权限缓存
    await clear_role_users_cache(role_id)

    return SuccessResponse(msg="权限分配成功")


@router.post("/roles/{role_id}/permission-groups", summary="为角色分配权限组")
async def assign_permission_groups(
        role_id: int,
        assign_data: RolePermissionGroupAssign,
        user_id: int = require_permission("role:update")
):
    """为角色分配权限组"""
    success = await RoleService.assign_permission_groups_to_role(role_id, assign_data.permission_group_ids)
    if not success:
        return ErrorResponse(msg="角色不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 清除该角色下所有用户的权限缓存
    await clear_role_users_cache(role_id)

    return SuccessResponse(msg="权限组分配成功")


# ==================== 权限管理 ==================== #

@router.get("/permissions/list", summary="获取权限列表")
async def get_permission_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量"),
        module: Optional[str] = Query(None, description="所属模块"),
        is_active: Optional[bool] = Query(None, description="是否激活"),
        user_id: int = require_permission("permission:list")
):
    """获取权限列表"""
    permissions, total = await PermissionService.get_permission_list(
        page=page,
        page_size=page_size,
        module=module,
        is_active=is_active,
    )

    permission_list = []
    for perm in permissions:
        perm_dict = await perm.to_dict()
        permission_list.append(perm_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": permission_list
    }

    return SuccessResponse(data=response_data)


@router.get("/permissions/all", summary="获取所有权限")
async def get_all_permissions(user_id: int = require_permission("permission:list")):
    """获取所有激活的权限"""
    permissions = await PermissionService.get_all_permissions()
    permission_list = [await perm.to_dict() for perm in permissions]
    return SuccessResponse(data=permission_list)


@router.get("/permissions/by-module", summary="按模块获取权限")
async def get_permissions_by_module(user_id: int = require_permission("permission:list")):
    """按模块分组获取所有权限"""
    permissions_by_module = await PermissionService.get_permissions_by_module()
    return SuccessResponse(data=permissions_by_module)


@router.post("/permissions", summary="创建权限")
async def create_permission(
        permission_data: PermissionCreate,
        user_id: int = require_permission("permission:create")
):
    """创建权限"""
    # 检查权限编码是否存在
    if await PermissionService.check_code_exists(permission_data.code):
        return ErrorResponse(msg="权限编码已存在", status_code=status.HTTP_400_BAD_REQUEST)

    permission = await PermissionService.create_permission(permission_data)
    perm_dict = await permission.to_dict()

    return SuccessResponse(data=perm_dict, msg="创建成功")


@router.put("/permissions/{permission_id}", summary="更新权限")
async def update_permission(
        permission_id: int,
        permission_data: PermissionUpdate,
        user_id: int = require_permission("permission:update")
):
    """更新权限"""
    permission = await PermissionService.update_permission(permission_id, permission_data)
    if not permission:
        return ErrorResponse(msg="权限不存在", status_code=status.HTTP_404_NOT_FOUND)

    perm_dict = await permission.to_dict()
    return SuccessResponse(data=perm_dict, msg="更新成功")


@router.delete("/permissions/{permission_id}", summary="删除权限")
async def delete_permission(
        permission_id: int,
        user_id: int = require_permission("permission:delete")
):
    """删除权限"""
    success = await PermissionService.delete_permission(permission_id)
    if not success:
        return ErrorResponse(msg="权限不存在", status_code=status.HTTP_404_NOT_FOUND)

    return SuccessResponse(msg="删除成功")


# ==================== 权限组管理 ==================== #

@router.get("/permission-groups/list", summary="获取权限组列表")
async def get_permission_group_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量"),
        name: Optional[str] = Query(None, description="权限组名称(模糊搜索)"),
        is_active: Optional[bool] = Query(None, description="是否激活"),
        user_id: int = require_permission("permission_group:list")
):
    """获取权限组列表"""
    groups, total = await PermissionGroupService.get_group_list(
        page=page,
        page_size=page_size,
        name=name,
        is_active=is_active,
    )

    group_list = []
    for group in groups:
        group_dict = await group.to_dict(include_permissions=True)
        group_list.append(group_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": group_list
    }

    return SuccessResponse(data=response_data)


@router.get("/permission-groups/all", summary="获取所有权限组")
async def get_all_permission_groups(user_id: int = require_permission("permission_group:list")):
    """获取所有激活的权限组"""
    groups = await PermissionGroupService.get_all_groups()
    group_list = [await group.to_dict() for group in groups]
    return SuccessResponse(data=group_list)


@router.get("/permission-groups/{group_id}", summary="获取权限组详情")
async def get_permission_group_detail(
        group_id: int,
        user_id: int = require_permission("permission_group:list")
):
    """获取权限组详情(包含权限列表)"""
    group = await PermissionGroupService.get_by_id(group_id)
    if not group:
        return ErrorResponse(msg="权限组不存在", status_code=status.HTTP_404_NOT_FOUND)

    group_dict = await group.to_dict(include_permissions=True)
    return SuccessResponse(data=group_dict)


@router.post("/permission-groups", summary="创建权限组")
async def create_permission_group(
        group_data: PermissionGroupCreate,
        user_id: int = require_permission("permission_group:create")
):
    """创建权限组"""
    # 检查权限组编码是否存在
    if await PermissionGroupService.check_code_exists(group_data.code):
        return ErrorResponse(msg="权限组编码已存在", status_code=status.HTTP_400_BAD_REQUEST)

    group = await PermissionGroupService.create_group(group_data)
    group_dict = await group.to_dict()

    return SuccessResponse(data=group_dict, msg="创建成功")


@router.put("/permission-groups/{group_id}", summary="更新权限组")
async def update_permission_group(
        group_id: int,
        group_data: PermissionGroupUpdate,
        user_id: int = require_permission("permission_group:update")
):
    """更新权限组"""
    group = await PermissionGroupService.update_group(group_id, group_data)
    if not group:
        return ErrorResponse(msg="权限组不存在", status_code=status.HTTP_404_NOT_FOUND)

    group_dict = await group.to_dict()
    return SuccessResponse(data=group_dict, msg="更新成功")


@router.delete("/permission-groups/{group_id}", summary="删除权限组")
async def delete_permission_group(
        group_id: int,
        user_id: int = require_permission("permission_group:delete")
):
    """删除权限组"""
    success = await PermissionGroupService.delete_group(group_id)
    if not success:
        return ErrorResponse(msg="权限组不存在", status_code=status.HTTP_404_NOT_FOUND)

    return SuccessResponse(msg="删除成功")


@router.post("/permission-groups/{group_id}/permissions", summary="为权限组分配权限")
async def assign_permissions_to_group(
        group_id: int,
        assign_data: PermissionGroupPermissionAssign,
        user_id: int = require_permission("permission_group:update")
):
    """为权限组分配权限"""
    success = await PermissionGroupService.assign_permissions_to_group(group_id, assign_data.permission_ids)
    if not success:
        return ErrorResponse(msg="权限组不存在", status_code=status.HTTP_404_NOT_FOUND)

    return SuccessResponse(msg="权限分配成功")


# ==================== 用户角色管理 ==================== #

@router.post("/users/{user_id}/roles", summary="为用户分配角色")
async def assign_roles_to_user(
        user_id: int,
        assign_data: UserRoleAssign,
        current_user_id: int = require_permission("user:update")
):
    """为用户分配角色"""
    user = await UserService.get_by_id(user_id)
    if not user:
        return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 清除原有角色
    await user.roles.clear()

    # 添加新角色
    if assign_data.role_ids:
        from base.core.users.models.rbac import Role
        roles = await Role.filter(id__in=assign_data.role_ids)
        await user.roles.add(*roles)

    # 清除用户权限缓存
    await clear_user_permission_cache(user_id)

    return SuccessResponse(msg="角色分配成功")


@router.get("/users/{user_id}/roles", summary="获取用户的角色")
async def get_user_roles(
        user_id: int,
        current_user_id: int = require_any_permission("user:list", "role:list")
):
    """获取用户的角色列表"""
    user = await UserService.get_by_id(user_id)
    if not user:
        return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)

    roles = await user.roles.all()
    role_list = [await role.to_dict() for role in roles]

    return SuccessResponse(data=role_list)


@router.get("/users/{user_id}/permissions", summary="获取用户的所有权限")
async def get_user_permissions(
        user_id: int,
        current_user_id: int = require_any_permission("user:list", "permission:list")
):
    """获取用户的所有权限编码（包含继承）"""
    permission_codes = await PermissionService.get_user_permissions_with_inheritance(user_id)
    return SuccessResponse(data=permission_codes)


@router.get("/my/permissions", summary="获取当前用户权限")
async def get_my_permissions(user_id: int = Depends(get_current_user_id)):
    """获取当前登录用户的所有权限编码"""
    permission_codes = await PermissionService.get_user_permissions_with_inheritance(user_id)
    return SuccessResponse(data=permission_codes)


@router.get("/my/roles", summary="获取当前用户角色")
async def get_my_roles(user_id: int = Depends(get_current_user_id)):
    """获取当前登录用户的角色列表"""
    user = await UserService.get_by_id(user_id)
    if not user:
        return ErrorResponse(msg="用户不存在", status_code=status.HTTP_404_NOT_FOUND)

    roles = await user.roles.filter(is_active=True).all()
    role_list = [await role.to_dict() for role in roles]

    return SuccessResponse(data=role_list)
