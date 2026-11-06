"""
部门模型
"""
from enum import Enum
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class OrgType(str, Enum):
    COMPANY = "company"
    DEPARTMENT = "department"


class Department(BaseModel, TimestampMixin):
    """部门模型"""
    name = fields.CharField(max_length=100, unique=True, description="部门名称", index=True)
    code = fields.CharField(max_length=50, unique=True, description="部门编码", index=True)
    parent_id = fields.IntField(null=True, description="父部门ID", index=True)
    type = fields.CharEnumField(OrgType, default=OrgType.DEPARTMENT, description="组织类型: company-公司, department-部门", index=True)
    level = fields.IntField(default=1, description="层级深度", index=True)
    leader_id = fields.IntField(null=True, description="部门负责人ID", index=True)
    phone = fields.CharField(max_length=20, null=True, description="联系电话")
    email = fields.CharField(max_length=255, null=True, description="邮箱")
    description = fields.TextField(null=True, description="部门描述")
    sort = fields.IntField(default=0, description="排序")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)

    class Meta:
        table = "department"
        ordering = ["sort", "id"]
