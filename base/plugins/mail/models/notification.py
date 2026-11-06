"""
通知模型 - mail.notification 的对应实现
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Notification(BaseModel, TimestampMixin):
    """通知（每条消息对每个收件人产生一条通知记录）"""
    message_id = fields.IntField(description="关联消息ID", index=True)
    user_id = fields.IntField(description="收件人用户ID", index=True)
    # 通知状态：ready(待发) / sent(已发) / canceled(取消) / exception(异常) / bounce(退信)
    notification_status = fields.CharField(
        max_length=20, default="ready", description="通知状态", index=True
    )
    is_read = fields.BooleanField(default=False, description="是否已读", index=True)
    read_datetime = fields.DatetimeField(null=True, description="已读时间")
    is_starred = fields.BooleanField(default=False, description="是否标星")

    class Meta:
        table = "mail_notification"
        # 同一消息同一收件人仅一条通知
        unique_together = (("message_id", "user_id"),)
        ordering = ["-created_at"]

    async def to_dict(self, include_message: bool = False):
        data = {
            "id": self.id,
            "message_id": self.message_id,
            "user_id": self.user_id,
            "notification_status": self.notification_status,
            "is_read": self.is_read,
            "read_datetime": self.read_datetime.strftime("%Y-%m-%d %H:%M:%S") if self.read_datetime else None,
            "is_starred": self.is_starred,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
        if include_message:
            try:
                from base.plugins.mail.models.message import Message
                msg = await Message.get_or_none(id=self.message_id)
                data["message"] = await msg.to_dict(include_author=True, include_subtype=True) if msg else None
            except Exception:
                data["message"] = None
        return data
