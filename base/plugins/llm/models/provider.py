"""
大模型厂商模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class LLMProvider(BaseModel, TimestampMixin):
    """大模型厂商表"""

    name = fields.CharField(max_length=50, unique=True, description="厂商名称")
    name_en = fields.CharField(max_length=50, unique=True, description="英文标识")
    logo_url = fields.CharField(max_length=255, null=True, description="厂商Logo URL")
    official_url = fields.CharField(max_length=255, null=True, description="官方网站")
    status = fields.CharField(max_length=20, default="active", description="状态: active/inactive/maintenance")
    description = fields.TextField(null=True, description="描述")

    class Meta:
        table = "llm_provider"

    def __str__(self):
        return self.name
