"""
角色权限模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
from enum import Enum


class DataScopeEnum(str, Enum):
    """数据权限范围枚举"""
    SELF = "self"           # 仅本人数据
    DEPT = "dept"           # 本部门数据
    DEPT_TREE = "dept_tree" # 本部门及下级部门数据
    CUSTOM = "custom"       # 自定义部门数据
    ALL = "all"             # 全部数据


class PermissionGroup(BaseModel, TimestampMixin):
    """权限组模型 - 用于批量分配权限"""
    name = fields.CharField(max_length=50, unique=True, description="权限组名称", index=True)
    code = fields.CharField(max_length=50, unique=True, description="权限组编码", index=True)
    description = fields.TextField(null=True, description="权限组描述")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    sort = fields.IntField(default=0, description="排序")

    # 多对多关系 - 权限组包含的权限
    permissions = fields.ManyToManyField(
        "models.Permission",
        related_name="groups",
        through="permission_group_permission"
    )

    class Meta:
        table = "permission_group"
        ordering = ["sort", "-created_at"]

    async def to_dict(self, include_permissions: bool = False):
        """转换为字典"""
        data = {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "is_active": self.is_active,
            "sort": self.sort,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

        if include_permissions:
            try:
                perms = await self.permissions.all()
                data["permissions"] = [await p.to_dict() for p in perms]
                data["permission_count"] = len(perms)
            except Exception:
                data["permissions"] = []
                data["permission_count"] = 0

        return data


class Role(BaseModel, TimestampMixin):
    """角色模型"""
    name = fields.CharField(max_length=50, unique=True, description="角色名称", index=True)
    code = fields.CharField(max_length=50, unique=True, description="角色编码", index=True)
    description = fields.TextField(null=True, description="角色描述")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    sort = fields.IntField(default=0, description="排序")

    # 角色继承 - 父角色ID
    parent_id = fields.IntField(null=True, description="父角色ID", index=True)

    # 数据权限范围
    data_scope = fields.CharField(
        max_length=20,
        default=DataScopeEnum.SELF.value,
        description="数据权限范围: self/dept/dept_tree/custom/all"
    )
    # 自定义部门ID列表（当data_scope为custom时使用）
    custom_dept_ids = fields.JSONField(null=True, description="自定义部门ID列表")

    # 多对多关系
    users = fields.ManyToManyField("models.User", related_name="roles", through="user_role")
    permissions = fields.ManyToManyField("models.Permission", related_name="roles", through="role_permission")
    permission_groups = fields.ManyToManyField(
        "models.PermissionGroup",
        related_name="roles",
        through="role_permission_group"
    )

    class Meta:
        table = "role"
        ordering = ["sort", "-created_at"]

    async def to_dict(self, include_permissions: bool = False, include_groups: bool = False):
        """转换为字典"""
        data = {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "is_active": self.is_active,
            "sort": self.sort,
            "parent_id": self.parent_id,
            "data_scope": self.data_scope,
            "custom_dept_ids": self.custom_dept_ids,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

        if include_permissions:
            try:
                perms = await self.permissions.all()
                data["permissions"] = [await p.to_dict() for p in perms]
            except Exception:
                data["permissions"] = []

        if include_groups:
            try:
                groups = await self.permission_groups.all()
                data["permission_groups"] = [await g.to_dict() for g in groups]
            except Exception:
                data["permission_groups"] = []

        return data

    async def get_parent(self):
        """获取父角色"""
        if self.parent_id:
            return await Role.filter(id=self.parent_id).first()
        return None

    async def get_children(self):
        """获取子角色列表"""
        return await Role.filter(parent_id=self.id).all()


class Permission(BaseModel, TimestampMixin):
    """权限模型"""
    name = fields.CharField(max_length=100, unique=True, description="权限名称", index=True)
    code = fields.CharField(max_length=100, unique=True, description="权限编码", index=True)
    description = fields.TextField(null=True, description="权限描述")
    module = fields.CharField(max_length=50, null=True, description="所属模块", index=True)
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)

    class Meta:
        table = "permission"
        ordering = ["module", "name"]

    async def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "module": self.module,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class DataPermissionRule(BaseModel, TimestampMixin):
    """数据权限规则模型 - 用于自定义数据过滤规则"""
    name = fields.CharField(max_length=50, description="规则名称", index=True)
    code = fields.CharField(max_length=50, unique=True, description="规则编码", index=True)
    description = fields.TextField(null=True, description="规则描述")
    table_name = fields.CharField(max_length=100, description="表名")
    field_name = fields.CharField(max_length=100, description="字段名")
    condition = fields.CharField(max_length=20, description="条件: eq/ne/in/not_in/like/dept_tree")
    value_source = fields.CharField(
        max_length=50,
        description="值来源: user.id/user.dept_id/role.custom_dept_ids/custom"
    )
    custom_value = fields.JSONField(null=True, description="自定义值（当value_source为custom时）")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)

    # 关联角色
    roles = fields.ManyToManyField(
        "models.Role",
        related_name="data_permission_rules",
        through="role_data_permission_rule"
    )

    class Meta:
        table = "data_permission_rule"
        ordering = ["table_name", "field_name"]

    async def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "table_name": self.table_name,
            "field_name": self.field_name,
            "condition": self.condition,
            "value_source": self.value_source,
            "custom_value": self.custom_value,
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class Menu(BaseModel, TimestampMixin):
    """菜单模型"""
    name = fields.CharField(max_length=50, description="菜单名称", index=True)
    path = fields.CharField(max_length=200, null=True, description="菜单路径")
    icon = fields.CharField(max_length=50, null=True, description="菜单图标")
    component = fields.CharField(max_length=200, null=True, description="组件路径")
    parent_id = fields.IntField(null=True, description="父菜单ID", index=True)
    sort = fields.IntField(default=0, description="排序")
    is_visible = fields.BooleanField(default=True, description="是否显示")
    is_cached = fields.BooleanField(default=True, description="是否缓存")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    menu_type = fields.CharField(max_length=20, default="menu", description="菜单类型: directory/menu/button")
    permission = fields.CharField(max_length=100, null=True, description="权限标识", index=True)

    class Meta:
        table = "menu"
        ordering = ["sort", "id"]

    async def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "icon": self.icon,
            "component": self.component,
            "parent_id": self.parent_id,
            "sort": self.sort,
            "is_visible": self.is_visible,
            "is_cached": self.is_cached,
            "is_active": self.is_active,
            "menu_type": self.menu_type,
            "permission": self.permission,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
