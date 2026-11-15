from tortoise import fields
from base.common.model import BaseModel


class EventRecord(BaseModel):
    event_uuid = fields.CharField(max_length=36, unique=True, index=True, description="事件唯一标识")
    event_name = fields.CharField(max_length=100, index=True, description="事件名称")
    payload = fields.JSONField(description="事件载荷")
    # Outbox 状态机：pending(待投递) → published(已入 ap.events) → consuming
    # → consumed / failed(可重试) / dead_letter(终态)。relay 只推 pending→published。
    status = fields.CharField(max_length=20, index=True, description="事件状态", default="pending")
    # 发布端幂等：DB 唯一约束（替代原 Redis 300s 键，与业务同事务生效）
    idempotency_key = fields.CharField(max_length=200, null=True, unique=True, description="发布幂等键")
    dispatch_attempts = fields.IntField(default=0, description="Outbox 投递尝试次数")
    locked_until = fields.DatetimeField(null=True, description="relay 租约到期时间(多副本抢占)")
    dispatched_at = fields.DatetimeField(null=True, description="实际投递进 ap.events 的时间")
    consuming_started_at = fields.DatetimeField(null=True, description="进入 consuming 的时间(悬挂回收判据)")
    retry_count = fields.IntField(default=0, description="重试次数")
    replay_count = fields.IntField(default=0, description="重放次数")
    error_message = fields.TextField(null=True, description="错误信息")
    published_at = fields.DatetimeField(description="消息产生时间(事务落库时间)")
    consumed_at = fields.DatetimeField(null=True, description="消费时间")
    next_retry_at = fields.DatetimeField(null=True, description="下次重试时间")
    processing_time_ms = fields.IntField(null=True, description="处理耗时(ms)")
    source_module = fields.CharField(max_length=50, null=True, index=True, description="来源模块")
    # 跨模块串联：与 audit_log / audit_input_layer / audit_output_layer 的 trace_id 同源。
    # 只有 HTTP 请求触发的事件才有值；后台作业/定时任务产生的事件为 NULL。
    trace_id = fields.CharField(max_length=100, null=True, index=True, description="全链路追踪ID")

    class Meta:
        table = "event_records"
        indexes = [
            ("event_name", "status"),
            ("status", "published_at"),
            ("status", "locked_until"),
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