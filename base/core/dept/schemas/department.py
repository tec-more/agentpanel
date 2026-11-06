"""
部门相关的Pydantic模型
"""
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class OrgType(str, Enum):
    COMPANY = "company"
    DEPARTMENT = "department"


class DepartmentBase(BaseModel):
    """部门基础模型"""
    name: str = Field(..., min_length=1, max_length=100, description="部门名称")
    code: str = Field(..., min_length=1, max_length=50, description="部门编码")
    parent_id: Optional[int] = Field(None, description="父部门ID")
    type: OrgType = Field(default=OrgType.DEPARTMENT, description="组织类型: company-公司, department-部门")
    leader_id: Optional[int] = Field(None, description="部门负责人ID")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    email: Optional[str] = Field(None, description="邮箱")
    description: Optional[str] = Field(None, description="部门描述")
    sort: int = Field(default=0, description="排序")


class DepartmentCreate(DepartmentBase):
    """创建部门模型"""
    pass


class DepartmentUpdate(BaseModel):
    """更新部门模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="部门名称")
    parent_id: Optional[int] = Field(None, description="父部门ID")
    type: Optional[OrgType] = Field(None, description="组织类型: company-公司, department-部门")
    leader_id: Optional[int] = Field(None, description="部门负责人ID")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    email: Optional[str] = Field(None, description="邮箱")
    description: Optional[str] = Field(None, description="部门描述")
    sort: Optional[int] = Field(None, description="排序")
    is_active: Optional[bool] = Field(None, description="是否激活")


class DepartmentResponse(BaseModel):
    """部门响应模型"""
    id: int
    name: str
    code: str
    parent_id: Optional[int] = None
    type: OrgType
    level: int
    leader_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    sort: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DepartmentTree(DepartmentResponse):
    """部门树形结构"""
    children: List["DepartmentTree"] = []
    leader_name: Optional[str] = None
