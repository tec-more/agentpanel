"""审核任务模型。"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ReviewTask(BaseModel, TimestampMixin):
    """审核任务：P1 中危内容的人工复核，放行后才可进入导出。"""
    content_version_id = fields.BigIntField(description="内容版本 ID", index=True)
    status = fields.CharField(max_length=32, default="pending", description="状态: pending/approved/rejected", index=True)
    reviewer_id = fields.BigIntField(null=True, description="审核人 ID")
    decision = fields.CharField(max_length=16, null=True, description="判定: approve/reject")
    reason = fields.TextField(null=True, description="驳回理由（驳回必填）")
    hit_count = fields.IntField(default=0, description="关联 P1 命中数")

    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr/org")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "contentops_review_task"
        ordering = ["-created_at"]
        indexes = [("owner_type", "owner_id", "status"), ("content_version_id", "status")]
