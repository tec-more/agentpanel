from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class CrmConfig(BaseModel, TimestampMixin):
    config_key = fields.CharField(max_length=100, unique=True, description="配置键")
    config_value = fields.CharField(max_length=500, description="配置值")
    description = fields.CharField(max_length=200, null=True, description="配置描述")

    class Meta:
        table = "crm_config"
        table_description = "CRM系统配置表"

    def __str__(self):
        return f"CrmConfig({self.config_key}={self.config_value})"