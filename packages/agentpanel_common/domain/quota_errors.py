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


class QuotaReservationConflict(Exception):
    """确定性 hold_id 重复使用但状态不可复用（明确“已存在”而非静默累加）。

    - pending：另一个调用正在预扣，尚未完成；
    - settled/released/expired：该预占已关闭，不允许复用同一 hold_id 重新预扣。
    """

    def __init__(self, hold_id: str, status: str):
        self.hold_id = hold_id
        self.status = status
        super().__init__(f"预占 {hold_id} 当前状态为 {status}，不能重复预占")

    @property
    def code(self) -> str:
        return "quota_reservation_in_progress" if self.status == "pending" else "quota_hold_closed"

    @property
    def data(self) -> dict:
        return {"error_code": self.code, "hold_id": self.hold_id, "status": self.status}
