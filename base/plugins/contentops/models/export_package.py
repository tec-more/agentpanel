"""导出快照模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ExportPackage(BaseModel, TimestampMixin):
    """导出快照：记录导出时的内容版本与规则版本，可重复下载，追溯"当时发的是什么"。"""
    content_id = fields.BigIntField(description="源内容 ID", index=True)
    platforms = fields.JSONField(default=list, description="本次导出的平台列表")
    version_ids = fields.JSONField(default=list, description="各平台对应的成品版本 ID")
    file_keys = fields.JSONField(default=dict, description="打包文件 key（对象存储路径）")
    rule_version = fields.CharField(max_length=64, null=True, description="导出时规则版本")
    expires_at = fields.DatetimeField(null=True, description="下载链接有效期")

    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")
    creator_id = fields.BigIntField(null=True, description="导出人 ID")

    class Meta:
        table = "contentops_export_package"
        ordering = ["-created_at"]
        indexes = [("owner_type", "owner_id", "content_id")]
