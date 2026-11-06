from tortoise import fields
from base.common.model import BaseModel


class ReplayAuditLog(BaseModel):
    operator = fields.CharField(max_length=100, index=True, description="操作人")
    event_uuids = fields.JSONField(description="重放事件UUID列表")
    reason = fields.TextField(description="重放原因")
    result = fields.CharField(max_length=10, description="重放结果(success/partial/failed)")
    success_count = fields.IntField(default=0, description="成功数量")
    fail_count = fields.IntField(default=0, description="失败数量")
    failed_event_uuids = fields.JSONField(null=True, description="失败事件UUID列表")

    class Meta:
        table = "event_replay_audit_logs"