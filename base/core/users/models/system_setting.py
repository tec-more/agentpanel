from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SystemSetting(BaseModel, TimestampMixin):
    """系统设置模型"""
    key = fields.CharField(max_length=100, unique=True, description="设置键", index=True)
    value = fields.TextField(null=True, description="设置值")
    name = fields.CharField(max_length=100, description="设置名称")
    description = fields.CharField(max_length=500, null=True, description="设置描述")
    setting_type = fields.CharField(max_length=50, default="string", description="设置类型: string/number/boolean/image")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    sort = fields.IntField(default=0, description="排序")

    class Meta:
        table = "system_setting"

    async def to_dict(self):
        """转换为字典"""
        data = {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "name": self.name,
            "description": self.description,
            "setting_type": self.setting_type,
            "is_active": self.is_active,
            "sort": self.sort,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        return data
