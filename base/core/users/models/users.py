from tortoise import fields
from tortoise.models import Model
from base.common.model import BaseModel,TimestampMixin

class User(BaseModel,TimestampMixin):
    username = fields.CharField(max_length=20, unique=True, description="用户名称", index=True)
    alias = fields.CharField(max_length=30, null=True, description="姓名", index=True)
    email = fields.CharField(max_length=255, unique=True, description="邮箱", index=True)
    phone = fields.CharField(max_length=20, null=True, description="电话", index=True)
    password = fields.CharField(max_length=128, null=True, description="密码")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    is_superuser = fields.BooleanField(default=False, description="是否为超级管理员", index=True)
    last_login = fields.DatetimeField(null=True, description="最后登录时间", index=True)
    dept_id = fields.IntField(null=True, description="部门ID", index=True)

    # 多对多关系 - 用户角色（关系定义在 Role 模型中）
    # roles: fields.ManyToManyRelation["Role"]

    class Meta:
        table = "user"

    async def to_dict(self, include_roles: bool = False):
        """转换为字典"""
        data = {
            "id": self.id,
            "username": self.username,
            "alias": self.alias,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "dept_id": self.dept_id,
            "last_login": self.last_login.strftime("%Y-%m-%d %H:%M:%S") if self.last_login else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

        # 获取部门信息
        if self.dept_id:
            from base.core.dept.models.department import Department
            dept = await Department.filter(id=self.dept_id).first()
            data["dept_name"] = dept.name if dept else None
        else:
            data["dept_name"] = None

        # 获取角色信息
        if include_roles:
            try:
                roles = await self.roles.all()
                data["roles"] = [{"id": r.id, "name": r.name, "code": r.code} for r in roles]
            except Exception:
                data["roles"] = []

        return data