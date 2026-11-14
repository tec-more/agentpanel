"""pydantic 消息契约（D7）。

约束：taskiq 默认 JSONSerializer 不认 `BaseModel` 实例，跨进程只传 dict；
在边界处用 `model_dump(mode="json")` / `model_validate` 往返。
"""
from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class JobMessage(BaseModel):
    """周期作业投递消息（M1 各作业无参；预留 payload 通道）。"""

    job_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventMessage(BaseModel):
    """事件分发消息（ap.events 队列；M3 真实分发契约）。

    与 EventRecord 一一对应：`event_uuid` 是消费端幂等键（终态 consumed /
    dead_letter 直接跳过）；worker 按 `event_name` 从进程内 handler registry
    （`EventBusAdapter.get_handlers`，由 register_ref / bind_manual 填充）取执行体。
    """

    event_uuid: str
    event_name: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    published_at: str = ""  # ISO-8601（仅审计展示用，不参与执行逻辑）


def serialize(model: BaseModel) -> Dict[str, Any]:
    """模型 → dict（mode="json" 保证 datetime/枚举等可序列化）。"""
    return model.model_dump(mode="json")


def deserialize_event(data: Dict[str, Any]) -> EventMessage:
    return EventMessage.model_validate(data)
