"""
Skill model
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Skill(BaseModel, TimestampMixin):
    verbose_name = "技能"
    """Skill model"""
    
    name = fields.CharField(max_length=100, description="Skill name")
    description = fields.TextField(null=True, description="Skill description")
    implementation = fields.TextField(null=True, description="Skill content (Markdown format)")
    status = fields.CharField(max_length=20, default="active", description="Status: active/inactive")
    category = fields.ForeignKeyField(
        "models.SkillCategory", 
        related_name="skills", 
        null=True, 
        on_delete=fields.SET_NULL,
        description="Skill category"
    )
    
    # 多对多关系 - Skill关联的Agents
    # Note: The related_name "agents" is already defined on the Agent side
    # and will be accessible here as well
    
    # 多对多关系 - Skill关联的ToolTags
    tool_tags = fields.ManyToManyField(
        "models.ToolTag",
        related_name="skills",
        through="skill_tool_tag",
        description="Tool tags bound to this skill"
    )
    
    class Meta:
        table = "skill"
    
    def __str__(self):
        return self.name
