"""事件载荷与 handler 返回值的公共契约（发布端唯一来源）。

分层约束
--------
- 后台手动发布 ``event_center.publish``：违反规则直接拒绝（raise ValueError）；
- 业务直调 ``event_bus.publish``：**不抛异常**打断业务事务，改为脱敏 + 体积保护；
- worker 记录 handler 返回值：同样脱敏，但用更小的体积上限。

安全约定
--------
凭据类字段在**落库前**遮蔽，避免后台事件详情 / 审计里出现明文。禁止字段集合
与 ``/v1/event-center/rules`` 展示的规则来自同一常量，不出现第二套阈值。
"""
from __future__ import annotations

import json
import re
from typing import Any

MAX_PAYLOAD_BYTES = 256 * 1024
MAX_RESULT_BYTES = 32 * 1024
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {"password", "secret", "token", "api_key", "private_key"}
)
MASKED_VALUE = "***"
_MAX_DEPTH = 8


def validate_payload(payload: Any) -> list[str]:
    """严格校验：JSON 对象、体积上限、禁止凭据字段。返回问题描述列表。"""
    problems: list[str] = []
    if not isinstance(payload, dict):
        return ["payload 必须是 JSON 对象"]
    try:
        raw = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        return [f"payload 不可序列化: {e}"]
    if _size(raw) > MAX_PAYLOAD_BYTES:
        problems.append(f"payload 超过 {MAX_PAYLOAD_BYTES} 字节上限")
    found = FORBIDDEN_PAYLOAD_KEYS.intersection({str(k).lower() for k in payload})
    if found:
        problems.append(f"payload 含禁止字段: {', '.join(sorted(found))}")
    return problems


def _size(raw: str) -> int:
    return len(raw.encode("utf-8"))


def _mask(obj: Any, depth: int = 0) -> Any:
    """递归遮蔽凭据类键；限制深度，防自引用 / 超深结构拖垮序列化。"""
    if depth >= _MAX_DEPTH:
        return "<max-depth>"
    if isinstance(obj, dict):
        return {
            k: (
                MASKED_VALUE
                if str(k).lower() in FORBIDDEN_PAYLOAD_KEYS
                else _mask(v, depth + 1)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_mask(v, depth + 1) for v in obj]
    return obj


def sanitize_payload(payload: dict) -> dict:
    """业务直调路径：脱敏 + 体积保护，**永不抛异常**。

    20+ 业务调用点在 ``@atomic()`` 内直连 ``event_bus.publish``；若这里因载荷
    含凭据或过大而抛错，整个业务事务会被回滚。因此采取「遮蔽而非拒绝」，
    并把结果 round-trip 成纯 JSON 基本类型，保证 JSONField 可安全入库。
    """
    try:
        masked = _mask(payload)
        raw = json.dumps(masked, ensure_ascii=False, default=str)
        if _size(raw) > MAX_PAYLOAD_BYTES:
            return {
                "__truncated__": True,
                "size_bytes": _size(raw),
                "preview": raw[:512],
            }
        decoded = json.loads(raw)
        return decoded if isinstance(decoded, dict) else {"value": decoded}
    except Exception as exc:
        return {"__serialize_error__": True, "detail": str(exc)[:200]}


def to_jsonable(value: Any, *, max_bytes: int = MAX_RESULT_BYTES) -> dict | None:
    """把任意 handler 返回值转成可入库 JSON：脱敏 + 深度 / 体积上限。

    返回 ``None`` 表示 handler 无返回值；超限只留预览，避免大对象撑爆
    ``event_inbox``。返回值一律包成 dict，便于后台直接渲染。
    """
    if value is None:
        return None
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str)
    except Exception as exc:
        return {"__serialize_error__": True, "detail": str(exc)[:200]}
    if _size(raw) > max_bytes:
        return {
            "__truncated__": True,
            "size_bytes": _size(raw),
            "preview": raw[:512],
            "type": type(value).__name__,
        }
    try:
        masked = _mask(json.loads(raw))
    except Exception:
        masked = {"value": raw[:512]}
    return masked if isinstance(masked, dict) else {"value": masked}


# 审计模块的 response_data / final_output 是 TextField，不是 JSONField；用同一套
# 禁止键名做文本级遮蔽，保证后台详情不会把凭据明文带出去。
_CREDENTIAL_TEXT_RE = re.compile(
    r"(?i)(password|secret|token|api_key|private_key)"
    r"(['\"]?\s*[:=]\s*['\"]?)([^\s'\"&,}]{1,200})"
)


def sanitize_text(value: Any, *, max_bytes: int = MAX_RESULT_BYTES) -> str | None:
    """文本脱敏 + 体积上限；用于审计响应正文等 TextField 字段。"""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    masked = _CREDENTIAL_TEXT_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}{MASKED_VALUE}", text
    )
    if _size(masked) <= max_bytes:
        return masked
    clipped = masked.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
    return f"{clipped}\n...<truncated>"


def sanitize_json(value: Any) -> Any:
    """JSONField / TextField 通用脱敏：dict/list 走递归遮蔽，字符串走文本遮蔽。"""
    if value is None:
        return None
    if isinstance(value, str):
        return sanitize_text(value)
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str)
        return _mask(json.loads(raw))
    except Exception as exc:
        return {"__serialize_error__": True, "detail": str(exc)[:200]}
