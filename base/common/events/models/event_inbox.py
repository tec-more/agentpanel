"""消费端 Inbox：一条消息 × 一个 handler 的执行凭据（幂等去重表）。

设计要点
--------
- ``dedup_key = f"{event_uuid}:{handler_key}"`` 单列唯一，避免依赖 ORM 的联合唯一
  特性，SQL 迁移与 ``generate_schemas`` 两条路径都能建出同一语义的约束。
- 消费端把「消息落库」和「状态修改」放进 DB 事务；handler 真实执行体仍必须在
  事务外（可能含 HTTP / 跨库 / 30s 超时），因此 Inbox 记录的是**执行凭据**而非
  事务性副作用：``done`` 的 handler 在重投时直接跳过，只有失败的才重试。
- ``status``：processing(已占用) / done(成功) / failed(失败，可重试)。
- ``return_value``：handler 的执行结果（后台事件详情展示用）。经
  ``payload_contract.to_jsonable`` 脱敏 + 体积上限后写入；无返回值写
  ``{"__no_return__": true}``，失败时写 NULL 由详情接口补说明对象。
- ``execution_time_ms`` / ``error_detail``：单 handler 的执行耗时与异常
  类型/堆栈（已截断），让「成功但没返回值」和「失败原因」在后台可区分。
"""
from tortoise import fields

from base.common.model import BaseModel


class EventInbox(BaseModel):
    dedup_key = fields.CharField(max_length=300, unique=True, description="event_uuid:handler_key")
    event_uuid = fields.CharField(max_length=36, index=True, description="事件唯一标识")
    handler_key = fields.CharField(max_length=200, description="序号:handler 名")
    status = fields.CharField(max_length=20, default="processing", description="处理状态")
    attempts = fields.IntField(default=1, description="该 handler 累计执行次数")
    error_message = fields.TextField(null=True, description="最近一次错误信息")
    error_detail = fields.TextField(null=True, description="异常类型与堆栈(已截断)")
    execution_time_ms = fields.IntField(null=True, description="该 handler 本次执行耗时(ms)")
    return_value = fields.JSONField(null=True, description="handler 返回值(已脱敏/限长)")
    finished_at = fields.DatetimeField(null=True, description="终态时间")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "event_inbox"
        indexes = [
            ("event_uuid", "status"),
        ]
