"""合规命中记录模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ComplianceHit(BaseModel, TimestampMixin):
    """合规命中：每次检测的命中项，绑定内容版本与规则版本。"""
    content_version_id = fields.BigIntField(description="内容版本 ID", index=True)
    rule_id = fields.BigIntField(null=True, description="规则 ID（语义/LLM 命中可为 NULL）")
    matched_text = fields.TextField(null=True, description="命中词/句")
    position = fields.IntField(null=True, description="命中位置（字符偏移）")
    level = fields.CharField(max_length=4, default="P2", description="风险等级: P0/P1/P2", index=True)
    basis = fields.TextField(null=True, description="依据条款")
    suggestion = fields.TextField(null=True, description="替换建议")
    confidence = fields.FloatField(null=True, description="置信度 0-1")
    channel = fields.CharField(max_length=16, default="text", description="命中通道: text/ocr/asr")
    rule_version = fields.CharField(max_length=64, null=True, description="规则版本")
    confirmed = fields.BooleanField(default=False, description="是否已人工处置")
    handled_by = fields.BigIntField(null=True, description="处置人 ID")

    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_compliance_hit"
        ordering = ["-created_at"]
        indexes = [("owner_type", "owner_id", "content_version_id"), ("content_version_id", "level")]
