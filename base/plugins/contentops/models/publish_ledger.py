"""发布台账与效果数据模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class PublishLedger(BaseModel, TimestampMixin):
    """发布台账：人工发布后的状态跟踪（不自动发布）。"""
    version_id = fields.BigIntField(description="成品版本 ID", index=True)
    platform = fields.CharField(max_length=32, description="平台标识", index=True)
    planned_at = fields.DatetimeField(null=True, description="计划发布时间")
    published_at = fields.DatetimeField(null=True, description="实际发布时间")
    status = fields.CharField(max_length=16, default="pending", description="状态: pending/published/abandoned", index=True)
    note = fields.TextField(null=True, description="备注")

    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_publish_ledger"
        ordering = ["-created_at"]
        indexes = [("owner_type", "owner_id", "status"), ("version_id", "platform")]


class EffectData(BaseModel, TimestampMixin):
    """效果数据：人工回填或第三方监测 CSV 导入。"""
    ledger_id = fields.BigIntField(description="台账 ID", index=True)
    views = fields.BigIntField(default=0, description="阅读/播放量")
    likes = fields.BigIntField(default=0, description="点赞")
    comments = fields.BigIntField(default=0, description="评论")
    favorites = fields.BigIntField(default=0, description="收藏")
    source = fields.CharField(max_length=16, default="manual", description="来源: manual/csv")
    stat_date = fields.DateField(null=True, description="统计数据日期")

    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_effect_data"
        ordering = ["-created_at"]
        indexes = [("owner_type", "owner_id", "ledger_id")]
