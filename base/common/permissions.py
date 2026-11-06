"""
权限验证依赖注入
提供便捷的权限检查功能，用于FastAPI路由
"""
from typing import List, Set, Optional
from fastapi import Depends, HTTPException, status, Request
from base.common.security import get_current_user_id
from base.common.cache import RedisCache


# 权限缓存键模板
PERM_CACHE_KEY = "rbac:user:permissions:{user_id}"
ROLE_CACHE_KEY = "rbac:user:roles:{user_id}"
DATA_SCOPE_CACHE_KEY = "rbac:user:data_scope:{user_id}"
PERM_CACHE_TTL = 3600  # 1小时


async def get_user_permissions_cached(user_id: int) -> List[str]:
    """
    获取用户权限（带缓存）

    Args:
        user_id: 用户ID

    Returns:
        权限编码列表
    """
    cache = await RedisCache.get_instance()

    # 如果Redis可用，尝试从缓存获取
    if RedisCache.is_enabled():
        cache_key = PERM_CACHE_KEY.format(user_id=user_id)
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    # 从数据库获取（包含继承的权限）
    from base.core.users.services.rbac_service import PermissionService
    permissions = await PermissionService.get_user_permissions_with_inheritance(user_id)

    # 如果Redis可用，写入缓存
    if RedisCache.is_enabled():
        await cache.set(cache_key, permissions, PERM_CACHE_TTL)
    return permissions


async def get_user_roles_cached(user_id: int) -> List[str]:
    """
    获取用户角色编码（带缓存）

    Args:
        user_id: 用户ID

    Returns:
        角色编码列表
    """
    cache = await RedisCache.get_instance()

    # 如果Redis可用，尝试从缓存获取
    if RedisCache.is_enabled():
        cache_key = ROLE_CACHE_KEY.format(user_id=user_id)
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    # 从数据库获取
    from base.core.users.services.user_service import UserService
    user = await UserService.get_by_id(user_id)
    if not user:
        return []

    roles = await user.roles.filter(is_active=True).all()
    role_codes = [r.code for r in roles]

    # 如果Redis可用，写入缓存
    if RedisCache.is_enabled():
        await cache.set(cache_key, role_codes, PERM_CACHE_TTL)
    return role_codes


async def get_user_data_scope_cached(user_id: int) -> dict:
    """
    获取用户数据权限范围（带缓存）

    Args:
        user_id: 用户ID

    Returns:
        数据权限范围字典
    """
    cache = await RedisCache.get_instance()

    # 如果Redis可用，尝试从缓存获取
    if RedisCache.is_enabled():
        cache_key = DATA_SCOPE_CACHE_KEY.format(user_id=user_id)
        cached = await cache.get(cache_key)
        if cached is not None:
            return cached

    # 从数据库获取
    from base.core.users.services.rbac_service import DataPermissionService
    data_scope = await DataPermissionService.get_user_data_scope(user_id)

    # 如果Redis可用，写入缓存
    if RedisCache.is_enabled():
        await cache.set(cache_key, data_scope, PERM_CACHE_TTL)
    return data_scope


def require_permission(*permissions: str):
    """
    要求用户具有所有指定权限

    用法:
        @router.post("/users")
        async def create_user(user_id: int = require_permission("user:create")):
            ...

    Args:
        permissions: 权限编码列表

    Returns:
        FastAPI依赖函数
    """
    async def dependency(
        request: Request,
        user_id: int = Depends(get_current_user_id)
    ) -> int:
        user_perms = await get_user_permissions_cached(user_id)

        # 超级管理员跳过检查（拥有通配符权限）
        if "*" in user_perms:
            return user_id

        # 检查是否拥有所有必需权限
        missing = set(permissions) - set(user_perms)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {', '.join(missing)}"
            )
        return user_id

    return Depends(dependency)


def require_any_permission(*permissions: str):
    """
    要求用户具有任一指定权限

    用法:
        @router.get("/data")
        async def get_data(user_id: int = require_any_permission("data:read", "data:admin")):
            ...

    Args:
        permissions: 权限编码列表

    Returns:
        FastAPI依赖函数
    """
    async def dependency(
        request: Request,
        user_id: int = Depends(get_current_user_id)
    ) -> int:
        user_perms = await get_user_permissions_cached(user_id)

        # 超级管理员跳过检查
        if "*" in user_perms:
            return user_id

        # 检查是否拥有任一权限
        if not set(permissions) & set(user_perms):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下权限之一: {', '.join(permissions)}"
            )
        return user_id

    return Depends(dependency)


def require_role(*roles: str):
    """
    要求用户具有任一指定角色

    用法:
        @router.delete("/users/{id}")
        async def delete_user(user_id: int = require_role("admin", "super_admin")):
            ...

    Args:
        roles: 角色编码列表

    Returns:
        FastAPI依赖函数
    """
    async def dependency(
        request: Request,
        user_id: int = Depends(get_current_user_id)
    ) -> int:
        user_roles = await get_user_roles_cached(user_id)

        # 检查是否拥有任一角色
        if not set(roles) & set(user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(roles)}"
            )
        return user_id

    return Depends(dependency)


def require_superuser():
    """
    要求用户是超级管理员

    用法:
        @router.post("/system/config")
        async def update_config(user_id: int = require_superuser()):
            ...

    Returns:
        FastAPI依赖函数
    """
    async def dependency(
        request: Request,
        user_id: int = Depends(get_current_user_id)
    ) -> int:
        from base.core.users.services.user_service import UserService
        user = await UserService.get_by_id(user_id)

        if not user or not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要超级管理员权限"
            )
        return user_id

    return Depends(dependency)


class PermissionChecker:
    """
    权限检查器类 - 用于更复杂的权限逻辑

    用法:
        checker = PermissionChecker(permissions=["user:list"], roles=["admin"])

        @router.get("/users")
        async def list_users(user_id: int = Depends(checker)):
            ...
    """

    def __init__(
        self,
        permissions: List[str] = None,
        roles: List[str] = None,
        require_all_permissions: bool = True,
        require_all_roles: bool = False
    ):
        """
        初始化权限检查器

        Args:
            permissions: 需要的权限列表
            roles: 需要的角色列表
            require_all_permissions: True=需要所有权限，False=需要任一权限
            require_all_roles: True=需要所有角色，False=需要任一角色
        """
        self.permissions = permissions or []
        self.roles = roles or []
        self.require_all_permissions = require_all_permissions
        self.require_all_roles = require_all_roles

    async def __call__(
        self,
        request: Request,
        user_id: int = Depends(get_current_user_id)
    ) -> int:
        """执行权限检查"""
        user_perms = await get_user_permissions_cached(user_id)

        # 超级管理员跳过检查
        if "*" in user_perms:
            return user_id

        # 检查权限
        if self.permissions:
            if self.require_all_permissions:
                missing = set(self.permissions) - set(user_perms)
                if missing:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"缺少权限: {', '.join(missing)}"
                    )
            else:
                if not set(self.permissions) & set(user_perms):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"需要以下权限之一: {', '.join(self.permissions)}"
                    )

        # 检查角色
        if self.roles:
            user_roles = await get_user_roles_cached(user_id)
            if self.require_all_roles:
                missing = set(self.roles) - set(user_roles)
                if missing:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"缺少角色: {', '.join(missing)}"
                    )
            else:
                if not set(self.roles) & set(user_roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"需要以下角色之一: {', '.join(self.roles)}"
                    )

        return user_id


# ==================== 缓存管理函数 ==================== #

async def clear_user_permission_cache(user_id: int):
    """
    清除单个用户的权限缓存

    Args:
        user_id: 用户ID
    """
    if not RedisCache.is_enabled():
        return
    cache = await RedisCache.get_instance()
    await cache.delete(PERM_CACHE_KEY.format(user_id=user_id))
    await cache.delete(ROLE_CACHE_KEY.format(user_id=user_id))
    await cache.delete(DATA_SCOPE_CACHE_KEY.format(user_id=user_id))


async def clear_role_users_cache(role_id: int):
    """
    清除角色下所有用户的权限缓存

    当角色权限变更时调用此函数

    Args:
        role_id: 角色ID
    """
    if not RedisCache.is_enabled():
        return
    from base.core.users.models.rbac import Role
    role = await Role.filter(id=role_id).prefetch_related("users").first()
    if role:
        users = await role.users.all()
        for user in users:
            await clear_user_permission_cache(user.id)


async def clear_all_permission_cache():
    """清除所有用户的权限缓存"""
    if not RedisCache.is_enabled():
        return
    cache = await RedisCache.get_instance()
    await cache.delete_pattern("rbac:user:*")


async def refresh_user_permission_cache(user_id: int):
    """
    刷新用户权限缓存

    Args:
        user_id: 用户ID
    """
    # 先清除缓存
    await clear_user_permission_cache(user_id)

    # 重新加载
    await get_user_permissions_cached(user_id)
    await get_user_roles_cached(user_id)
    await get_user_data_scope_cached(user_id)


# ==================== 数据权限辅助函数 ==================== #

async def get_data_filter(user_id: int, dept_field: str = "dept_id") -> dict:
    """
    获取用户的数据过滤条件

    用于在查询时添加数据权限过滤

    Args:
        user_id: 用户ID
        dept_field: 部门字段名

    Returns:
        Tortoise ORM过滤条件字典
    """
    from base.core.users.services.rbac_service import DataPermissionService
    data_scope = await get_user_data_scope_cached(user_id)
    data_scope["user_id"] = user_id
    return DataPermissionService.build_data_filter(data_scope, dept_field)
