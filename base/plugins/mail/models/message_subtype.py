"""
消息子类型模型 - mail.message.subtype 的对应实现
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class MessageSubtype(BaseModel, TimestampMixin):
    """消息子类型（消息的分类标签，如「评论」「订单已创建」「审批已通过」）"""
    name = fields.CharField(max_length=100, description="显示名")
    code = fields.CharField(max_length=100, unique=True, description="编码", index=True)
    description = fields.TextField(null=True, description="描述")
    # 适用的业务模型表名（NULL=通用）
    model = fields.CharField(max_length=100, null=True, description="适用模型表名", index=True)
    # 是否为评论默认子类型
    default = fields.BooleanField(default=False, description="是否评论默认子类型")
    internal = fields.BooleanField(default=False, description="是否仅内部可见")
    sequence = fields.IntField(default=10, description="排序")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)
    is_system = fields.BooleanField(default=False, description="是否系统预设（不可删除）")

    class Meta:
        table = "mail_message_subtype"
        ordering = ["sequence", "id"]

    async def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "model": self.model,
            "default": self.default,
            "internal": self.internal,
            "sequence": self.sequence,
            "is_active": self.is_active,
            "is_system": self.is_system,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
