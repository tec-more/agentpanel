"""
Memory model
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Memory(BaseModel, TimestampMixin):
    verbose_name = "记忆"
    """Memory model"""
    
    agent = fields.ForeignKeyField("models.Agent", related_name="memories", description="Associated agent")
    content = fields.TextField(description="Memory content")
    type = fields.CharField(max_length=50, default="short_term", description="Memory type: short_term/long_term")
    importance = fields.FloatField(default=0.5, description="Memory importance (0-1)")
    recall_count = fields.IntField(default=0, description="Recall count")
    last_recalled_at = fields.DatetimeField(null=True, description="Last recalled time")
    
    # 记忆模式：public（公共记忆）/private（私有记忆）
    memory_mode = fields.CharField(max_length=20, default="public", description="Memory mode: public/private")
    
    # 用户关联：customer用户使用customer_id，管理用户使用user_id
    customer_id = fields.BigIntField(null=True, description="Customer ID for private memory")
    user_id = fields.BigIntField(null=True, description="User ID for private memory")
    
    class Meta:
        table = "memory"
    
    def __str__(self):
        return f"Memory for {self.agent.name} ({self.memory_mode})"