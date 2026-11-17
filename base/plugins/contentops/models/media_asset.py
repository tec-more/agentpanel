"""素材资产模型：图片/封面/视频成片/适配产物统一存储与归属隔离。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class MediaAsset(BaseModel, TimestampMixin):
    """素材资产。

    文件本体存 storage/contentops/media/ 下，DB 只存相对路径与元信息。
    kind: image(正文图) / cover(封面) / video(外部成片) / adapted(适配产物)
    """
    content_id = fields.BigIntField(null=True, description="关联源内容 ID（上传时可选，稍后绑定）", index=True)
    kind = fields.CharField(max_length=16, default="image", description="素材类型: image/cover/video/adapted", index=True)
    filename = fields.CharField(max_length=255, description="存储文件名（uuid.ext）")
    rel_path = fields.CharField(max_length=512, description="相对 storage/contentops/media 的路径")
    url = fields.CharField(max_length=512, description="访问 URL（/api/v1/contentops/media/file/{id}）")
    content_type = fields.CharField(max_length=64, description="MIME 类型")
    size_bytes = fields.BigIntField(default=0, description="文件字节数")
    width = fields.IntField(null=True, description="图片/视频宽")
    height = fields.IntField(null=True, description="图片/视频高")
    duration_sec = fields.FloatField(null=True, description="视频时长（秒）")
    tags = fields.JSONField(default=list, description="素材标签（租户内复用）")
    ocr_text = fields.TextField(null=True, description="OCR/ASR 提取文本缓存（合规检测用）")
    ocr_status = fields.CharField(max_length=16, default="pending",
                                  description="OCR 状态: pending/done/failed/unsupported")
    extra = fields.JSONField(default=dict, description="扩展元信息（适配参数/父素材ID等）")

    # M8 双主体归属
    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")
    uploader_id = fields.BigIntField(null=True, description="上传人 ID")

    class Meta:
        table = "contentops_media_asset"
        ordering = ["-created_at"]
        indexes = [
            ("owner_type", "owner_id"),
            ("content_id", "kind"),
            ("kind", "ocr_status"),
        ]
