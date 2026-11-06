"""
第三方平台智能体模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
from base.plugins.thirdparty.models.platform import ThirdPartyPlatform


class ThirdPartyAgent(BaseModel, TimestampMixin):
    verbose_name = "第三方智能体"
    """第三方平台智能体表"""

    name = fields.CharField(max_length=100, description="智能体名称")
    platform = fields.ForeignKeyField("models.ThirdPartyPlatform", related_name="agents", description="所属平台")
    agent_id = fields.CharField(max_length=100, description="智能体ID")
    access_url = fields.CharField(max_length=255, description="智能体访问地址")
    status = fields.CharField(max_length=20, default="active", description="状态: active/inactive")
    description = fields.TextField(null=True, description="描述")
    config = fields.JSONField(null=True, description="额外配置")

    class Meta:
        table = "thirdparty_agent"

    def __str__(self):
        return self.name