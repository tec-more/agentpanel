"""
Tool model
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Tool(BaseModel, TimestampMixin):
    verbose_name = "工具"
    """Tool model"""
    name = fields.CharField(max_length=100, unique=True, description="Tool identifier")
    display_name = fields.CharField(max_length=100, description="Display name")
    description = fields.TextField(null=True, description="Tool description")
    func_path = fields.CharField(max_length=255, null=True, description="Function path")
    parameters = fields.JSONField(null=True, description="Parameter configuration")
    enabled = fields.BooleanField(default=True, description="Is enabled")
    
    tags = fields.ManyToManyField(
        "models.ToolTag",
        related_name="tools",
        through="tool_tool_tag"
    )
    
    class Meta:
        table = "tool"
        ordering = ["name"]
