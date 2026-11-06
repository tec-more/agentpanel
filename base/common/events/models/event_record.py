from tortoise import fields
from base.common.model import BaseModel


class EventRecord(BaseModel):
    event_uuid = fields.CharField(max_length=36, unique=True, index=True, description="事件唯一标识")
    event_name = fields.CharField(max_length=100, index=True, description="事件名称")
    payload = fields.JSONField(description="事件载荷")
    status = fields.CharField(max_length=20, index=True, description="事件状态", default="pending")
    retry_count = fields.IntField(default=0, description="重试次数")
    replay_count = fields.IntField(default=0, description="重放次数")
    error_message = fields.TextField(null=True, description="错误信息")
    published_at = fields.DatetimeField(description="发布时间")
    consumed_at = fields.DatetimeField(null=True, description="消费时间")
    next_retry_at = fields.DatetimeField(null=True, description="下次重试时间")
    processing_time_ms = fields.IntField(null=True, description="处理耗时(ms)")
    source_module = fields.CharField(max_length=50, null=True, index=True, description="来源模块")

    class Meta:
        table = "event_records"
        indexes = [
            ("event_name", "status"),
            ("status", "published_at"),
        ]

    async def to_dict(self, **kwargs):
        d = await super().to_dict(**kwargs)
        if d.get("payload") and isinstance(d["payload"], str):
            import json
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
        return d