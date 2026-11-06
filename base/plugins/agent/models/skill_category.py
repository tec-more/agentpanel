"""
Skill Category model
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class SkillCategory(BaseModel, TimestampMixin):
    verbose_name = "技能分类"
    """Skill Category model"""
    
    name = fields.CharField(max_length=100, description="Category name")
    description = fields.TextField(null=True, description="Category description")
    parent_id = fields.IntField(null=True, description="Parent category ID")
    sort_order = fields.IntField(default=0, description="Sort order")
    status = fields.CharField(max_length=20, default="active", description="Status: active/inactive")
    
    class Meta:
        table = "skill_category"
        unique_together = (("name",),)  # 确保分类名称唯一
    
    def __str__(self):
        return self.name
