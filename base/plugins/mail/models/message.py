"""
消息模型 - mail.message 的对应实现
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Message(BaseModel, TimestampMixin):
    """消息（任意业务记录线程上的一条评论或通知）"""
    subject = fields.CharField(max_length=255, null=True, description="主题")
    body = fields.TextField(null=True, description="正文（纯文本或简单HTML）")
    author_id = fields.IntField(description="发送者用户ID（系统消息为0）", index=True)
    # 通用外键：关联业务记录（model 表名 + res_id）
    model = fields.CharField(max_length=100, null=True, description="关联业务表名", index=True)
    res_id = fields.IntField(null=True, description="关联业务记录ID", index=True)
    # 消息类型：notification（系统通知）/ comment（用户评论）/ email
    message_type = fields.CharField(max_length=20, default="notification", description="消息类型", index=True)
    # 子类型（外键软关联 MessageSubtype）
    subtype_id = fields.IntField(null=True, description="子类型ID", index=True)
    # 父消息（回复链）
    parent_id = fields.IntField(null=True, description="父消息ID", index=True)
    is_internal = fields.BooleanField(default=False, description="是否内部备注")
    # 附件元数据（简化版，不依赖独立附件表）
    attachment_ids = fields.JSONField(default=list, description="附件元数据列表")
    # 业务记录显示名（冗余，便于列表展示）
    record_name = fields.CharField(max_length=255, null=True, description="业务记录显示名")

    class Meta:
        table = "mail_message"
        ordering = ["-created_at"]

    async def to_dict(self, include_author: bool = False, include_subtype: bool = False):
        """转换为字典

        include_author: 是否附带发送者用户基本信息
        include_subtype: 是否附带子类型详情
        """
        data = {
            "id": self.id,
            "subject": self.subject,
            "body": self.body,
            "author_id": self.author_id,
            "model": self.model,
            "res_id": self.res_id,
            "message_type": self.message_type,
            "subtype_id": self.subtype_id,
            "parent_id": self.parent_id,
            "is_internal": self.is_internal,
            "attachment_ids": self.attachment_ids,
            "record_name": self.record_name,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_author and self.author_id:
            try:
                from base.core.users.models.users import User
                user = await User.get_or_none(id=self.author_id)
                if user:
                    data["author"] = {
                        "id": user.id,
                        "username": user.username,
                        "alias": user.alias,
                        "email": user.email,
                    }
                else:
                    data["author"] = {"id": 0, "username": "system", "alias": "系统"}
            except Exception:
                data["author"] = {"id": self.author_id}
        if include_subtype and self.subtype_id:
            try:
                from base.plugins.mail.models.message_subtype import MessageSubtype
                subtype = await MessageSubtype.get_or_none(id=self.subtype_id)
                data["subtype"] = await subtype.to_dict() if subtype else None
            except Exception:
                data["subtype"] = None
        return data
