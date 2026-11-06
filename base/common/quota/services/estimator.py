"""
字符启发式 Token 预估（C-05 配套）

溯源：docs/arch/03 §2.9（N3-6 已确认）
- tokens ≈ chars/3.5（英文）、chars/1.5（中文），保守取高
- 偏差 ±20% 符合 NFR；结算必须用供应商真实 usage 修正
- 任意模型可用、零依赖；tiktoken 仅作可选辅助（本模块不引入）
"""
import math
from typing import Iterable, Mapping, Any

# 启发式除数：中文（CJK）保守 1.5，英文/其他 3.5
CJK_DIVISOR = 1.5
OTHER_DIVISOR = 3.5


def _is_cjk(ch: str) -> bool:
    """CJK 统一表意文字及常见全角符号区间"""
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF
        or 0x3400 <= o <= 0x4DBF
        or 0x3000 <= o <= 0x303F
        or 0xFF00 <= o <= 0xFFEF
    )


def estimate_tokens(text: str, reserve_output: int = 0) -> int:
    """
    估算文本 token 数（保守取高：中文按 /1.5，其余按 /3.5，向上取整）

    Args:
        text: 输入文本（prompt/消息/上下文拼接）
        reserve_output: 预期输出预留（通常取节点 max_tokens）
    """
    if not text:
        return int(reserve_output)
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    tokens = math.ceil(cjk / CJK_DIVISOR + other / OTHER_DIVISOR)
    return tokens + int(reserve_output)


def estimate_messages_tokens(
    messages: Iterable[Mapping[str, Any]], reserve_output: int = 0
) -> int:
    """
    估算消息列表 token 数（role/content 等字段拼接后走字符启发式）

    供 T6 引擎/LLM 网关在模型调用前预估（F7 前置拦截）。
    """
    total = 0
    for msg in messages or []:
        for value in msg.values():
            if isinstance(value, str):
                total += estimate_tokens(value)
    return total + int(reserve_output)
