from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class IntegrationConfig(BaseModel, TimestampMixin):
    verbose_name = "集成配置"
    config_key = fields.CharField(max_length=128, unique=True, description="配置键")
    config_value = fields.CharField(max_length=256, description="配置值")
    description = fields.TextField(null=True, description="描述")

    class Meta:
        table = "finance_integration_configs"

    async def to_dict(self):
        return {
            "id": self.id,
            "config_key": self.config_key,
            "config_value": self.config_value,
            "description": self.description,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }