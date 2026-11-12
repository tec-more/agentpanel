"""事件订阅与发布规则（平台级唯一契约，PLR-14 / PLR-21）。

所有插件与后台管理动作都必须遵守这里定义的规则：

1. 事件名：小写点分多段 ``<domain>.<action>``，只描述「发生了什么」，
   不带插件技术参数；业务单据字段放 payload，由插件级定义。
2. 载荷：必须是 JSON 可序列化对象，键为字符串，大小受限，禁止放凭据。
3. 幂等：发布方可传 ``idempotency_key``；同一键重复投递不得产生重复副作用。
4. 投递：至少一次；重试上限、消费确认由事件总线承担；内存降级通道不保证确认。
5. 隔离：订阅方异常不得冒泡到发布方；停用订阅不得产生副作用。
6. 订阅声明：插件在 manifest.events.subscribe 声明；后台新增走 manual 来源。
"""
from __future__ import annotations

import json
from typing import Any

from base.common.plugin_contract import is_valid_event_name

MAX_PAYLOAD_BYTES = 256 * 1024
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_MS = 30_000
FORBIDDEN_PAYLOAD_KEYS = {"password", "secret", "token", "api_key", "private_key"}

RULES: dict[str, Any] = {
    "event_name": {
        "pattern": r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
        "example": "sales.paid / model.created / plugin.enabled",
        "rule": "小写点分多段，禁止大写、空格、通配符与查询参数",
    },
    "payload": {
        "type": "object(JSON)",
        "max_bytes": MAX_PAYLOAD_BYTES,
        "forbidden_keys": sorted(FORBIDDEN_PAYLOAD_KEYS),
        "rule": "必须是 JSON 对象；禁止携带凭据类字段；业务字段由插件级定义",
    },
    "idempotency": {
        "header": "idempotency_key",
        "rule": "同一幂等键重复投递不得产生重复副作用；未传时由事件总线生成 event_uuid",
    },
    "delivery": {
        "semantics": "at-least-once",
        "max_retries": DEFAULT_MAX_RETRIES,
        "timeout_ms": DEFAULT_TIMEOUT_MS,
        "ack": "RabbitMQ 通道落 EventRecord.consumed_at；内存降级通道不保证确认",
    },
    "isolation": {
        "rule": "订阅方异常逐个捕获，不冒泡到发布方；停用订阅直接跳过",
        "reference": "base/common/events/event_bus.py:publish",
    },
    "subscription": {
        "sources": ["declared", "manual"],
        "rule": "插件订阅必须在 manifest.events.subscribe 声明；后台新增为 manual",
        "lifecycle": "插件启用即注册、禁用即注销，均由 base/core/events/registry.py 统一执行",
    },
    "publish": {
        "entry": "base/core/events/registry.py:EventCenter.publish",
        "rule": "平台统一入口；兼容既有 event_bus.publish 调用，逐步迁移",
    },
}


def validate_event_name(event_name: str) -> list[str]:
    if not is_valid_event_name(event_name):
        return [f"非法事件名 {event_name!r}：应为小写点分格式，如 sales.paid"]
    return []


def validate_payload(payload: Any) -> list[str]:
    """校验载荷：JSON 对象、体积上限、禁止凭据字段。"""
    problems: list[str] = []
    if not isinstance(payload, dict):
        return ["payload 必须是 JSON 对象"]
    try:
        raw = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        return [f"payload 不可序列化: {e}"]
    if len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        problems.append(f"payload 超过 {MAX_PAYLOAD_BYTES} 字节上限")
    found = FORBIDDEN_PAYLOAD_KEYS.intersection({str(k).lower() for k in payload})
    if found:
        problems.append(f"payload 含禁止字段: {', '.join(sorted(found))}")
    return problems


def validate_subscription(event_name: str, handler_ref: str | None = None) -> list[str]:
    problems = validate_event_name(event_name)
    if handler_ref and ":" not in handler_ref:
        problems.append("handler_ref 必须是 'module:callable' 格式")
    return problems
