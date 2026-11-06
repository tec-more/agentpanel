"""
角色权限服务层
"""
from typing import Optional, List, Tuple, Set
from tortoise.expressions import Q

from base.core.users.models.rbac import Role, Permission, Menu, PermissionGroup, DataPermissionRule
from base.core.users.models.users import User
from base.core.users.schemas.rbac import (
    RoleCreate, RoleUpdate, PermissionCreate, PermissionUpdate,
    PermissionGroupCreate, PermissionGroupUpdate
)


class RoleService:
    """角色服务类"""

    @staticmethod
    async def get_by_id(role_id: int) -> Optional[Role]:
        """根据ID获取角色"""
        return await Role.filter(id=role_id).first()

    @staticmethod
    async def get_by_code(code: str) -> Optional[Role]:
        """根据编码获取角色"""
        return await Role.filter(code=code).first()

    @staticmethod
    async def create_role(role_data: RoleCreate) -> Role:
        """创建角色"""
        role = await Role.create(
            name=role_data.name,
            code=role_data.code,
            description=role_data.description,
            sort=role_data.sort,
            parent_id=role_data.parent_id,
            data_scope=role_data.data_scope,
            custom_dept_ids=role_data.custom_dept_ids,
        )

        # 关联权限
        if role_data.permission_ids:
            permissions = await Permission.filter(id__in=role_data.permission_ids)
            await role.permissions.add(*permissions)

        # 关联权限组
        if role_data.permission_group_ids:
            groups = await PermissionGroup.filter(id__in=role_data.permission_group_ids)
            await role.permission_groups.add(*groups)

        return role

    @staticmethod
    async def update_role(role_id: int, role_data: RoleUpdate) -> Optional[Role]:
        """更新角色"""
        role = await Role.filter(id=role_id).first()
        if not role:
            return None

        update_data = role_data.model_dump(exclude_unset=True, exclude={'permission_ids', 'permission_group_ids'})
        await role.update_from_dict(update_data).save()

        # 更新权限关联
        if role_data.permission_ids is not None:
            await role.permissions.clear()
            if role_data.permission_ids:
                permissions = await Permission.filter(id__in=role_data.permission_ids)
                await role.permissions.add(*permissions)

        # 更新权限组关联
        if role_data.permission_group_ids is not None:
            await role.permission_groups.clear()
            if role_data.permission_group_ids:
                groups = await PermissionGroup.filter(id__in=role_data.permission_group_ids)
                await role.permission_groups.add(*groups)

        return role

    @staticmethod
    async def delete_role(role_id: int) -> bool:
        """删除角色"""
        # 检查是否有子角色
        has_children = await Role.filter(parent_id=role_id).exists()
        if has_children:
            return False

        deleted_count = await Role.filter(id=role_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_role_list(
            page: int = 1,
            page_size: int = 10,
            name: Optional[str] = None,
            is_active: Optional[bool] = None,
    ) -> Tuple[List[Role], int]:
        """获取角色列表"""
        query = Role.all()

        if name:
            query = query.filter(name__icontains=name)
        if is_active is not None:
            query = query.filter(is_active=is_active)

        total = await query.count()

        offset = (page - 1) * page_size
        roles = await query.offset(offset).limit(page_size).order_by('sort', '-created_at')

        return roles, total

    @staticmethod
    async def get_role_tree() -> List[dict]:
        """获取角色树形结构"""
        roles = await Role.filter(is_active=True).order_by('sort', 'id')

        # 构建树形结构
        role_list = []
        for role in roles:
            role_dict = await role.to_dict()
            role_dict['children'] = []
            role_list.append(role_dict)

        # 构建父子关系
        role_map = {role['id']: role for role in role_list}
        tree = []

        for role in role_list:
            parent_id = role.get('parent_id')
            if parent_id and parent_id in role_map:
                role_map[parent_id]['children'].append(role)
            else:
                tree.append(role)

        return tree

    @staticmethod
    async def assign_permissions_to_role(role_id: int, permission_ids: List[int]) -> bool:
        """为角色分配权限"""
        role = await Role.filter(id=role_id).first()
        if not role:
            return False

        # 清除原有权限
        await role.permissions.clear()

        # 添加新权限
        if permission_ids:
            permissions = await Permission.filter(id__in=permission_ids)
            await role.permissions.add(*permissions)

        return True

    @staticmethod
    async def assign_permission_groups_to_role(role_id: int, group_ids: List[int]) -> bool:
        """为角色分配权限组"""
        role = await Role.filter(id=role_id).first()
        if not role:
            return False

        # 清除原有权限组
        await role.permission_groups.clear()

        # 添加新权限组
        if group_ids:
            groups = await PermissionGroup.filter(id__in=group_ids)
            await role.permission_groups.add(*groups)

        return True

    @staticmethod
    async def get_role_permissions(role_id: int) -> List[Permission]:
        """获取角色的所有权限"""
        role = await Role.filter(id=role_id).prefetch_related('permissions').first()
        if not role:
            return []
        return await role.permissions.all()

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查角色编码是否存在"""
        query = Role.filter(code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def get_all_permissions_with_inheritance(role_id: int) -> List[str]:
        """获取角色的所有权限（包含继承的权限）"""
        permission_codes: Set[str] = set()

        async def collect_permissions(rid: int, visited: Set[int]):
            if rid in visited:
                return
            visited.add(rid)

            role = await Role.filter(id=rid, is_active=True).first()
            if not role:
                return

            # 获取直接权限
            perms = await role.permissions.filter(is_active=True).all()
            permission_codes.update([p.code for p in perms])

            # 获取权限组中的权限
            groups = await role.permission_groups.filter(is_active=True).all()
            for group in groups:
                group_perms = await group.permissions.filter(is_active=True).all()
                permission_codes.update([p.code for p in group_perms])

            # 递归获取父角色权限
            if role.parent_id:
                await collect_permissions(role.parent_id, visited)

        await collect_permissions(role_id, set())
        return list(permission_codes)


class PermissionService:
    """权限服务类"""

    @staticmethod
    async def get_by_id(permission_id: int) -> Optional[Permission]:
        """根据ID获取权限"""
        return await Permission.filter(id=permission_id).first()

    @staticmethod
    async def get_by_code(code: str) -> Optional[Permission]:
        """根据编码获取权限"""
        return await Permission.filter(code=code).first()

    @staticmethod
    async def create_permission(permission_data: PermissionCreate) -> Permission:
        """创建权限"""
        permission = await Permission.create(
            name=permission_data.name,
            code=permission_data.code,
            description=permission_data.description,
            module=permission_data.module,
        )
        return permission

    @staticmethod
    async def update_permission(permission_id: int, permission_data: PermissionUpdate) -> Optional[Permission]:
        """更新权限"""
        permission = await Permission.filter(id=permission_id).first()
        if not permission:
            return None

        update_data = permission_data.model_dump(exclude_unset=True)
        await permission.update_from_dict(update_data).save()
        return permission

    @staticmethod
    async def delete_permission(permission_id: int) -> bool:
        """删除权限"""
        deleted_count = await Permission.filter(id=permission_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_permission_list(
            page: int = 1,
            page_size: int = 10,
            module: Optional[str] = None,
            is_active: Optional[bool] = None,
    ) -> Tuple[List[Permission], int]:
        """获取权限列表"""
        query = Permission.all()

        if module:
            query = query.filter(module=module)
        if is_active is not None:
            query = query.filter(is_active=is_active)

        total = await query.count()

        offset = (page - 1) * page_size
        permissions = await query.offset(offset).limit(page_size).order_by('module', 'name')

        return permissions, total

    @staticmethod
    async def get_all_permissions() -> List[Permission]:
        """获取所有权限"""
        return await Permission.filter(is_active=True).all()

    @staticmethod
    async def get_permissions_by_module() -> dict:
        """按模块分组获取所有权限"""
        permissions = await Permission.filter(is_active=True).order_by('module', 'name')
        result = {}
        for perm in permissions:
            module = perm.module or "其他"
            if module not in result:
                result[module] = []
            result[module].append(await perm.to_dict())
        return result

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查权限编码是否存在"""
        query = Permission.filter(code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def get_user_permissions(user_id: int) -> List[str]:
        """获取用户的所有权限编码（不含继承）"""
        user = await User.filter(id=user_id).prefetch_related('roles__permissions').first()
        if not user:
            return []

        # 如果是超级管理员,返回所有权限
        if user.is_superuser:
            all_permissions = await Permission.filter(is_active=True).all()
            return [perm.code for perm in all_permissions]

        # 获取用户所有角色的权限
        permission_codes = set()
        roles = await user.roles.filter(is_active=True).prefetch_related('permissions')
        for role in roles:
            permissions = await role.permissions.filter(is_active=True)
            permission_codes.update([perm.code for perm in permissions])

        return list(permission_codes)

    @staticmethod
    async def get_user_permissions_with_inheritance(user_id: int) -> List[str]:
        """获取用户所有权限（包含角色继承和权限组）"""
        user = await User.filter(id=user_id).first()
        if not user:
            return []

        # 超级管理员返回通配符
        if user.is_superuser:
            return ["*"]

        permission_codes: Set[str] = set()
        roles = await user.roles.filter(is_active=True).all()

        for role in roles:
            # 获取角色的所有权限（包含继承）
            role_perms = await RoleService.get_all_permissions_with_inheritance(role.id)
            permission_codes.update(role_perms)

        return list(permission_codes)

    @staticmethod
    async def batch_create_permissions(permissions_data: List[dict]) -> List[Permission]:
        """批量创建权限"""
        permissions = []
        for data in permissions_data:
            # 检查是否已存在
            exists = await Permission.filter(code=data['code']).exists()
            if not exists:
                perm = await Permission.create(**data)
                permissions.append(perm)
        return permissions


class PermissionGroupService:
    """权限组服务类"""

    @staticmethod
    async def get_by_id(group_id: int) -> Optional[PermissionGroup]:
        """根据ID获取权限组"""
        return await PermissionGroup.filter(id=group_id).first()

    @staticmethod
    async def get_by_code(code: str) -> Optional[PermissionGroup]:
        """根据编码获取权限组"""
        return await PermissionGroup.filter(code=code).first()

    @staticmethod
    async def create_group(group_data: PermissionGroupCreate) -> PermissionGroup:
        """创建权限组"""
        group = await PermissionGroup.create(
            name=group_data.name,
            code=group_data.code,
            description=group_data.description,
            sort=group_data.sort,
        )

        # 关联权限
        if group_data.permission_ids:
            permissions = await Permission.filter(id__in=group_data.permission_ids)
            await group.permissions.add(*permissions)

        return group

    @staticmethod
    async def update_group(group_id: int, group_data: PermissionGroupUpdate) -> Optional[PermissionGroup]:
        """更新权限组"""
        group = await PermissionGroup.filter(id=group_id).first()
        if not group:
            return None

        update_data = group_data.model_dump(exclude_unset=True, exclude={'permission_ids'})
        await group.update_from_dict(update_data).save()

        # 更新权限关联
        if group_data.permission_ids is not None:
            await group.permissions.clear()
            if group_data.permission_ids:
                permissions = await Permission.filter(id__in=group_data.permission_ids)
                await group.permissions.add(*permissions)

        return group

    @staticmethod
    async def delete_group(group_id: int) -> bool:
        """删除权限组"""
        deleted_count = await PermissionGroup.filter(id=group_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_group_list(
            page: int = 1,
            page_size: int = 10,
            name: Optional[str] = None,
            is_active: Optional[bool] = None,
    ) -> Tuple[List[PermissionGroup], int]:
        """获取权限组列表"""
        query = PermissionGroup.all()

        if name:
            query = query.filter(name__icontains=name)
        if is_active is not None:
            query = query.filter(is_active=is_active)

        total = await query.count()

        offset = (page - 1) * page_size
        groups = await query.offset(offset).limit(page_size).order_by('sort', '-created_at')

        return groups, total

    @staticmethod
    async def get_all_groups() -> List[PermissionGroup]:
        """获取所有权限组"""
        return await PermissionGroup.filter(is_active=True).order_by('sort', 'name')

    @staticmethod
    async def check_code_exists(code: str, exclude_id: Optional[int] = None) -> bool:
        """检查权限组编码是否存在"""
        query = PermissionGroup.filter(code=code)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def assign_permissions_to_group(group_id: int, permission_ids: List[int]) -> bool:
        """为权限组分配权限"""
        group = await PermissionGroup.filter(id=group_id).first()
        if not group:
            return False

        await group.permissions.clear()
        if permission_ids:
            permissions = await Permission.filter(id__in=permission_ids)
            await group.permissions.add(*permissions)

        return True


class DataPermissionService:
    """数据权限服务"""

    # 数据权限范围优先级
    SCOPE_PRIORITY = {
        "self": 0,
        "dept": 1,
        "dept_tree": 2,
        "custom": 3,
        "all": 4
    }

    @staticmethod
    async def get_user_data_scope(user_id: int) -> dict:
        """获取用户数据权限范围"""
        user = await User.filter(id=user_id).first()
        if not user:
            return {"scope": "self", "dept_ids": [], "user_id": user_id}

        if user.is_superuser:
            return {"scope": "all", "dept_ids": [], "user_id": user_id, "user_dept_id": user.dept_id}

        # 取最大权限范围
        max_scope = "self"
        custom_dept_ids: Set[int] = set()

        roles = await user.roles.filter(is_active=True).all()
        for role in roles:
            current_priority = DataPermissionService.SCOPE_PRIORITY.get(role.data_scope, 0)
            max_priority = DataPermissionService.SCOPE_PRIORITY.get(max_scope, 0)

            if current_priority > max_priority:
                max_scope = role.data_scope

            # 收集自定义部门ID
            if role.data_scope == "custom" and role.custom_dept_ids:
                custom_dept_ids.update(role.custom_dept_ids)

        return {
            "scope": max_scope,
            "dept_ids": list(custom_dept_ids),
            "user_id": user_id,
            "user_dept_id": user.dept_id
        }

    @staticmethod
    def build_data_filter(data_scope: dict, dept_field: str = "dept_id") -> dict:
        """
        构建数据过滤条件

        Args:
            data_scope: 数据权限范围
            dept_field: 部门字段名

        Returns:
            Tortoise ORM过滤条件字典
        """
        scope = data_scope.get("scope", "self")

        if scope == "all":
            return {}
        elif scope == "self":
            return {"created_by": data_scope.get("user_id")}
        elif scope == "dept":
            user_dept_id = data_scope.get("user_dept_id")
            if user_dept_id:
                return {dept_field: user_dept_id}
            return {"created_by": data_scope.get("user_id")}
        elif scope == "dept_tree":
            user_dept_id = data_scope.get("user_dept_id")
            if user_dept_id:
                dept_ids = DataPermissionService._get_dept_tree_ids(user_dept_id)
                return {f"{dept_field}__in": dept_ids}
            return {"created_by": data_scope.get("user_id")}
        elif scope == "custom":
            dept_ids = data_scope.get("dept_ids", [])
            if dept_ids:
                return {f"{dept_field}__in": dept_ids}
            return {"created_by": data_scope.get("user_id")}

        return {"created_by": data_scope.get("user_id")}

    @staticmethod
    def _get_dept_tree_ids(dept_id: int) -> List[int]:
        """
        获取部门及其所有子部门ID

        注意：这是同步方法，在实际使用中需要异步版本
        """
        # 这里简化处理，实际应该递归查询部门树
        # 需要配合 DepartmentService 使用
        return [dept_id]

    @staticmethod
    async def get_dept_tree_ids_async(dept_id: int) -> List[int]:
        """获取部门及其所有子部门ID（异步）"""
        from base.core.dept.models.department import Department

        dept_ids = [dept_id]

        async def get_children(parent_id: int):
            children = await Department.filter(parent_id=parent_id, is_active=True).all()
            for child in children:
                dept_ids.append(child.id)
                await get_children(child.id)

        await get_children(dept_id)
        return dept_ids

    @staticmethod
    async def apply_data_filter(query, user_id: int, dept_field: str = "dept_id"):
        """
        应用数据权限过滤

        Args:
            query: Tortoise ORM查询对象
            user_id: 用户ID
            dept_field: 部门字段名

        Returns:
            过滤后的查询对象
        """
        data_scope = await DataPermissionService.get_user_data_scope(user_id)
        filter_dict = DataPermissionService.build_data_filter(data_scope, dept_field)

        if filter_dict:
            return query.filter(**filter_dict)
        return query
