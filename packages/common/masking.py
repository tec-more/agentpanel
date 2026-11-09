"""密钥脱敏与校验工具

统一约定：
- 对外回显、审计、日志只允许出现遮蔽值；
- 校验失败的消息不得包含原值；
- fingerprint 用于在不暴露明文的前提下比对密钥是否一致。
"""
import hashlib
import re
from typing import Any, Dict

# 这些字段一旦落审计/日志必须脱敏（按字段名精确匹配，避免误伤 token 计数等普通字段）
SENSITIVE_FIELD_NAMES = {
    "password",
    "api_key",
    "api_secret",
    "access_token",
    "app_secret",
    "client_secret",
    "refresh_token",
    "secret_key",
}

# 密钥中不允许出现的字符：空白与控制字符
_INVALID_SECRET_RE = re.compile(r"[\s\x00-\x1f\x7f]", re.UNICODE)
_MIN_SECRET_LEN = 8
_MAX_SECRET_LEN = 512


def mask_secret(value: Any, head: int = 4, tail: int = 4) -> str:
    """遮蔽密钥：前 head + **** + 后 tail；过短或非字符串返回 ****"""
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    if len(text) < max(8, head + tail + 4):
        return "****"
    return f"{text[:head]}****{text[-tail:]}"


def is_masked(value: Any) -> bool:
    """判断是否为遮蔽值（含 ****）"""
    return isinstance(value, str) and "****" in value


def fingerprint(value: Any) -> str:
    """密钥指纹（sha256 前 12 位），空值返回空串"""
    if not value:
        return ""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def validate_secret(value: Any, field: str = "api_key") -> str | None:
    """校验密钥长度与格式；None/空串视为未填写。

    Raises:
        ValueError: 校验失败，消息不含原值
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if is_masked(text):
        raise ValueError(f"{field} 不能是遮蔽值")
    if len(text) < _MIN_SECRET_LEN or len(text) > _MAX_SECRET_LEN:
        raise ValueError(f"{field} 长度必须在 {_MIN_SECRET_LEN}-{_MAX_SECRET_LEN} 之间")
    if _INVALID_SECRET_RE.search(text):
        raise ValueError(f"{field} 不能包含空白或控制字符")
    return text


def redact_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """按字段名遮蔽字典中的敏感字段（递归处理嵌套 dict/list）"""
    if not isinstance(data, dict):
        return data
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if str(key).lower() in SENSITIVE_FIELD_NAMES:
            result[key] = mask_secret(value) if value else value
        elif isinstance(value, dict):
            result[key] = redact_fields(value)
        elif isinstance(value, list):
            result[key] = [
                redact_fields(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result
