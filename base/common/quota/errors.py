"""
M9 配额异常 - 42901 语义

溯源：docs/arch/04 §2.3 统一错误
    {"code":42901,"message":"额度不足，预计消耗 12000 tokens，剩余 8000","data":{"item":"llm_tokens"}}
错误码段位：429xx 配额/限流（R-15）。
"""
from typing import Optional

QUOTA_ERROR_CODE = 42901


class QuotaError(Exception):
    """
    配额不足/拦截异常（前置阻断，R-09：预占先于一切外部调用）

    - code: 42901（额度不足）
    - item: 触发拦截的配额项（如 llm_tokens/concurrency/daily_runs）
    - remaining: 当前剩余额度
    - estimated: 本次预计消耗
    """

    def __init__(
        self,
        item: str,
        remaining: float = 0,
        estimated: float = 0,
        message: Optional[str] = None,
    ):
        self.code = QUOTA_ERROR_CODE
        self.item = item
        self.remaining = remaining
        self.estimated = estimated
        self.message = message or (
            f"额度不足，预计消耗 {int(estimated)} {item}，剩余 {int(remaining)}"
        )
        super().__init__(self.message)

    @property
    def data(self) -> dict:
        return {
            "item": self.item,
            "remaining": self.remaining,
            "estimated": self.estimated,
        }
