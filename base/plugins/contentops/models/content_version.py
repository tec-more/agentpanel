"""平台成品版本模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ContentVersion(BaseModel, TimestampMixin):
    """平台成品版本：源内容适配到某平台的一份成品，可多次生成、可回退。"""
    content_id = fields.BigIntField(description="源内容 ID", index=True)
    platform = fields.CharField(max_length=32, description="平台标识", index=True)
    payload = fields.JSONField(default=dict, description="成品载荷（标题/正文/话题/图片/封面/成片等）")
    is_adapted = fields.BooleanField(default=False, description="是否自适应生成")
    parent_id = fields.BigIntField(null=True, description="父版本 ID（diff 回退链）")
    diff = fields.JSONField(default=list, description="相对父版本的 原句→改句 diff 列表")
    rule_version = fields.CharField(max_length=64, null=True, description="生成时规则版本")
    confirmed = fields.BooleanField(default=False, description="是否已人工确认（导出唯一出口）")
    status = fields.CharField(max_length=32, default="pending", description="状态", index=True)

    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_content_version"
        ordering = ["-created_at"]
        indexes = [("owner_type", "owner_id", "content_id"), ("content_id", "platform")]
