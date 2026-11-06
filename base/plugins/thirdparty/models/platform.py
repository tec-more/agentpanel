"""
第三方平台模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ThirdPartyPlatform(BaseModel, TimestampMixin):
    verbose_name = "第三方平台"
    """第三方平台表"""

    name = fields.CharField(max_length=50, unique=True, description="平台名称")
    platform_type = fields.CharField(max_length=20, description="平台类型: saas/local")
    api_key = fields.CharField(max_length=255, description="API密钥")
    base_url = fields.CharField(max_length=255, description="平台基础URL")
    status = fields.CharField(max_length=20, default="active", description="状态: active/inactive")
    description = fields.TextField(null=True, description="描述")
    config = fields.JSONField(null=True, description="额外配置")

    class Meta:
        table = "thirdparty_platform"

    def __str__(self):
        return self.name