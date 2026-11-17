"""源内容模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ContentItem(BaseModel, TimestampMixin):
    """源内容：一次创作的结构化原始内容。"""
    title = fields.CharField(max_length=512, description="标题")
    body = fields.TextField(description="正文（富文本/HTML）")
    summary = fields.TextField(null=True, description="摘要")
    media = fields.JSONField(default=list, description="图片/视频引用列表")
    topics = fields.JSONField(default=list, description="话题标签")
    cover = fields.CharField(max_length=512, null=True, description="封面 URL")
    status = fields.CharField(max_length=32, default="draft", description="状态", index=True)

    # M8 双主体归属
    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")
    creator_id = fields.BigIntField(null=True, description="创建人用户 ID")

    class Meta:
        table = "contentops_content_item"
        ordering = ["-created_at"]
        indexes = [("owner_type", "owner_id", "status")]
