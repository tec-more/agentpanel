"""
Tool Tag models
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ToolTag(BaseModel, TimestampMixin):
    verbose_name = "工具标签"
    """工具标签模型"""
    name = fields.CharField(max_length=100, unique=True, description="标签名称")
    description = fields.TextField(null=True, description="标签描述")
    color = fields.CharField(max_length=20, default="#409eff", description="标签颜色")
    sort_order = fields.IntField(default=0, description="排序")
    enabled = fields.BooleanField(default=True, description="是否启用")
    
    class Meta:
        table = "tool_tag"
        ordering = ["sort_order", "name"]
    
    def __str__(self):
        return self.name
