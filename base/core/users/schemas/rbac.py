"""
角色权限相关的Pydantic模型
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class DataScopeEnum(str, Enum):
    """数据权限范围枚举"""
    SELF = "self"           # 仅本人数据
    DEPT = "dept"           # 本部门数据
    DEPT_TREE = "dept_tree" # 本部门及下级部门数据
    CUSTOM = "custom"       # 自定义部门数据
    ALL = "all"             # 全部数据


# ==================== 角色相关 ==================== #

class RoleBase(BaseModel):
    """角色基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    code: str = Field(..., min_length=1, max_length=50, description="角色编码")
    description: Optional[str] = Field(None, description="角色描述")
    sort: int = Field(default=0, description="排序")


class RoleCreate(RoleBase):
    """创建角色模型"""
    parent_id: Optional[int] = Field(None, description="父角色ID（用于角色继承）")
    data_scope: str = Field(default=DataScopeEnum.SELF.value, description="数据权限范围")
    custom_dept_ids: Optional[List[int]] = Field(None, description="自定义部门ID列表")
    permission_ids: List[int] = Field(default=[], description="权限ID列表")
    permission_group_ids: List[int] = Field(default=[], description="权限组ID列表")


class RoleUpdate(BaseModel):
    """更新角色模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, description="角色描述")
    is_active: Optional[bool] = Field(None, description="是否激活")
    sort: Optional[int] = Field(None, description="排序")
    parent_id: Optional[int] = Field(None, description="父角色ID")
    data_scope: Optional[str] = Field(None, description="数据权限范围")
    custom_dept_ids: Optional[List[int]] = Field(None, description="自定义部门ID列表")
    permission_ids: Optional[List[int]] = Field(None, description="权限ID列表")
    permission_group_ids: Optional[List[int]] = Field(None, description="权限组ID列表")


class RoleResponse(BaseModel):
    """角色响应模型"""
    id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool
    sort: int
    parent_id: Optional[int] = None
    data_scope: str = DataScopeEnum.SELF.value
    custom_dept_ids: Optional[List[int]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RoleWithPermissions(RoleResponse):
    """带权限的角色响应模型"""
    permissions: List["PermissionResponse"] = []
    permission_groups: List["PermissionGroupResponse"] = []


class RoleTree(RoleResponse):
    """角色树形结构"""
    children: List["RoleTree"] = []


# ==================== 权限相关 ==================== #

class PermissionBase(BaseModel):
    """权限基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="权限名称")
    code: str = Field(..., min_length=1, max_length=100, description="权限编码（建议格式: module:action）")
    description: Optional[str] = Field(None, description="权限描述")
    module: Optional[str] = Field(None, max_length=50, description="所属模块")


class PermissionCreate(PermissionBase):
    """创建权限模型"""
    pass


class PermissionUpdate(BaseModel):
    """更新权限模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="权限名称")
    description: Optional[str] = Field(None, description="权限描述")
    module: Optional[str] = Field(None, max_length=50, description="所属模块")
    is_active: Optional[bool] = Field(None, description="是否激活")


class PermissionResponse(BaseModel):
    """权限响应模型"""
    id: int
    name: str
    code: str
    description: Optional[str] = None
    module: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PermissionByModule(BaseModel):
    """按模块分组的权限"""
    module: str
    permissions: List[PermissionResponse]


# ==================== 权限组相关 ==================== #

class PermissionGroupBase(BaseModel):
    """权限组基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="权限组名称")
    code: str = Field(..., min_length=1, max_length=50, description="权限组编码")
    description: Optional[str] = Field(None, description="权限组描述")
    sort: int = Field(default=0, description="排序")


class PermissionGroupCreate(PermissionGroupBase):
    """创建权限组模型"""
    permission_ids: List[int] = Field(default=[], description="权限ID列表")


class PermissionGroupUpdate(BaseModel):
    """更新权限组模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="权限组名称")
    description: Optional[str] = Field(None, description="权限组描述")
    is_active: Optional[bool] = Field(None, description="是否激活")
    sort: Optional[int] = Field(None, description="排序")
    permission_ids: Optional[List[int]] = Field(None, description="权限ID列表")


class PermissionGroupResponse(BaseModel):
    """权限组响应模型"""
    id: int
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool
    sort: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PermissionGroupWithPermissions(PermissionGroupResponse):
    """带权限列表的权限组响应模型"""
    permissions: List[PermissionResponse] = []
    permission_count: int = 0


# ==================== 菜单相关 ==================== #

class MenuBase(BaseModel):
    """菜单基础模型"""
    name: str = Field(..., min_length=1, max_length=50, description="菜单名称")
    path: str = Field(..., max_length=200, description="菜单路径")
    icon: Optional[str] = Field(None, max_length=50, description="菜单图标")
    component: Optional[str] = Field(None, max_length=200, description="组件路径")
    parent_id: Optional[int] = Field(None, description="父菜单ID")
    sort: int = Field(default=0, description="排序")
    is_hidden: bool = Field(default=False, description="是否隐藏")
    menu_type: str = Field(default="menu", description="菜单类型: directory/menu/button")
    permission_code: Optional[str] = Field(None, max_length=100, description="权限编码")


class MenuCreate(MenuBase):
    """创建菜单模型"""
    pass


class MenuUpdate(BaseModel):
    """更新菜单模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="菜单名称")
    path: Optional[str] = Field(None, max_length=200, description="菜单路径")
    icon: Optional[str] = Field(None, max_length=50, description="菜单图标")
    component: Optional[str] = Field(None, max_length=200, description="组件路径")
    parent_id: Optional[int] = Field(None, description="父菜单ID")
    sort: Optional[int] = Field(None, description="排序")
    is_hidden: Optional[bool] = Field(None, description="是否隐藏")
    is_active: Optional[bool] = Field(None, description="是否激活")
    menu_type: Optional[str] = Field(None, description="菜单类型")
    permission_code: Optional[str] = Field(None, description="权限编码")


class MenuResponse(BaseModel):
    """菜单响应模型"""
    id: int
    name: str
    path: str
    icon: Optional[str] = None
    component: Optional[str] = None
    parent_id: Optional[int] = None
    sort: int
    is_hidden: bool
    is_active: bool
    menu_type: str
    permission_code: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MenuTree(MenuResponse):
    """菜单树形结构"""
    children: List["MenuTree"] = []


# ==================== 用户角色分配 ==================== #

class UserRoleAssign(BaseModel):
    """用户角色分配模型"""
    user_id: int = Field(..., description="用户ID")
    role_ids: List[int] = Field(..., description="角色ID列表")


class RolePermissionAssign(BaseModel):
    """角色权限分配模型"""
    role_id: int = Field(..., description="角色ID")
    permission_ids: List[int] = Field(..., description="权限ID列表")


class RolePermissionGroupAssign(BaseModel):
    """角色权限组分配模型"""
    role_id: int = Field(..., description="角色ID")
    permission_group_ids: List[int] = Field(..., description="权限组ID列表")


class PermissionGroupPermissionAssign(BaseModel):
    """权限组权限分配模型"""
    group_id: int = Field(..., description="权限组ID")
    permission_ids: List[int] = Field(..., description="权限ID列表")


# ==================== 数据权限相关 ==================== #

class DataScopeUpdate(BaseModel):
    """更新数据权限范围"""
    role_id: int = Field(..., description="角色ID")
    data_scope: str = Field(..., description="数据权限范围")
    custom_dept_ids: Optional[List[int]] = Field(None, description="自定义部门ID列表")


class UserDataScope(BaseModel):
    """用户数据权限范围"""
    scope: str
    dept_ids: List[int] = []
    user_id: int
    user_dept_id: Optional[int] = None


# ==================== 批量操作 ==================== #

class BatchPermissionCreate(BaseModel):
    """批量创建权限"""
    permissions: List[PermissionCreate] = Field(..., description="权限列表")


class BatchResult(BaseModel):
    """批量操作结果"""
    success_count: int = Field(default=0, description="成功数量")
    fail_count: int = Field(default=0, description="失败数量")
    failed_items: List[str] = Field(default=[], description="失败项")
