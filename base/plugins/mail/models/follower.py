"""
关注者模型 - mail.followers 的对应实现
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class Follower(BaseModel, TimestampMixin):
    """关注者（用户关注某条业务记录，按子类型订阅通知）"""
    model = fields.CharField(max_length=100, description="关注业务表名", index=True)
    res_id = fields.IntField(description="业务记录ID", index=True)
    user_id = fields.IntField(description="关注者用户ID", index=True)
    # 订阅的子类型ID列表（空列表=订阅全部子类型）
    subtype_ids = fields.JSONField(default=list, description="订阅的子类型ID列表")

    class Meta:
        table = "mail_follower"
        # 防止同一用户重复关注同一记录
        unique_together = (("model", "res_id", "user_id"),)
        indexes = (("model", "res_id"),)

    async def to_dict(self, include_user: bool = False):
        data = {
            "id": self.id,
            "model": self.model,
            "res_id": self.res_id,
            "user_id": self.user_id,
            "subtype_ids": self.subtype_ids,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
        if include_user:
            try:
                from base.core.users.models.users import User
                user = await User.get_or_none(id=self.user_id)
                if user:
                    data["user"] = {
                        "id": user.id,
                        "username": user.username,
                        "alias": user.alias,
                        "email": user.email,
                    }
            except Exception:
                data["user"] = {"id": self.user_id}
        return data
