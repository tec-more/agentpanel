"""事件订阅关系（后台可管理）。

- declared：来自插件 manifest.events.subscribe，随插件启停同步；
- manual：后台新增，handler_ref 指向 module:callable，由注册表动态绑定。
"""
from tortoise import fields

from base.common.model import BaseModel, TimestampMixin


class EventSubscription(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, unique=True, index=True, description="订阅唯一名称")
    event_name = fields.CharField(max_length=100, index=True, description="订阅的事件名")
    subscriber = fields.CharField(max_length=50, index=True, description="订阅方/插件名")
    handler_ref = fields.CharField(max_length=300, null=True, description="module:callable")
    source = fields.CharField(max_length=20, default="declared", index=True, description="declared/manual")
    is_enabled = fields.BooleanField(default=True, index=True, description="是否生效")
    is_system = fields.BooleanField(default=False, description="系统内置，不可删除")
    max_retries = fields.IntField(default=3, description="最大重试次数")
    timeout_ms = fields.IntField(default=30000, description="处理超时(毫秒)")
    description = fields.TextField(null=True, description="说明")
    extra = fields.JSONField(default=dict, description="扩展信息")

    class Meta:
        table = "event_subscriptions"
        ordering = ["subscriber", "event_name"]

    async def to_dict(self, **kwargs) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "event_name": self.event_name,
            "subscriber": self.subscriber,
            "handler_ref": self.handler_ref,
            "source": self.source,
            "is_enabled": self.is_enabled,
            "is_system": self.is_system,
            "max_retries": self.max_retries,
            "timeout_ms": self.timeout_ms,
            "description": self.description,
            "extra": self.extra,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
