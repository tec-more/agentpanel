"""
Agent model
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Agent(BaseModel, TimestampMixin):
    verbose_name = "智能体"
    """Agent model"""
    
    name = fields.CharField(max_length=100, description="Agent name")
    description = fields.TextField(null=True, description="Agent description")
    status = fields.CharField(max_length=20, default="active", description="Status: active/inactive")
    graph_definition = fields.JSONField(null=True, description="Agent graph definition (nodes and edges)")
    memory_capacity = fields.IntField(default=100, description="Memory capacity")
    
    # 默认记忆模式：public（公共记忆）/private（私有记忆）
    default_memory_mode = fields.CharField(max_length=20, default="public", description="Default memory mode: public/private")
    
    config = fields.JSONField(null=True, description="Agent configuration (tools, etc.)")

    # ===== T1 双主体归属与发布态扩展（溯源 02-§4.3 / Q-C）=====
    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")
    # 发布状态（M12）：unpublished 未发布 / published 已发布 / suspended 已停用
    publish_status = fields.CharField(max_length=20, default="unpublished", description="发布状态: unpublished/published/suspended")

    # 多对多关系 - Agent拥有的Skills
    skills = fields.ManyToManyField(
        "models.Skill",
        related_name="agents",
        through="agent_skill"
    )
    
    class Meta:
        table = "agent"
    
    def __str__(self):
        return self.name