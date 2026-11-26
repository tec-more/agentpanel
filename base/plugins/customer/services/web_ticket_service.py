"""一次性 Web 登录票据服务（dsh → 客户门户免登）。

设计红线：
- 网关虚拟 key（dgw.*）与客户 JWT 双向隔离：签发只接受已鉴权的 cus 主体；
  换发只产出标准 cus JWT，绝不接受 dgw.* 或 Harness 客户端凭据。
- 明文票据只出现在签发响应里；库中只存 SHA-256。
- 60 秒有效、单次消费；消费采用条件更新 CAS，并发重放只有一个请求成功。
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from base.plugins.customer.models.web_ticket import CustomerWebTicket

TICKET_TTL_SECONDS = 60
DEFAULT_REDIRECT = "/dashboard"


def _naive_utc(value: datetime) -> datetime:
    """把库里读回的时间归一成 naive UTC，避免与 utcnow() 比较时
    'can't compare offset-naive and offset-aware datetimes'。

    写入用的是 datetime.utcnow()（UTC naive）。openGauss 经 asyncpg 读回
    DatetimeField 时会 attach 本地时区（如 Asia/Shanghai +08:00），但墙上
    时钟数值仍是写入时的 UTC 值——所以只能**直接剥掉 tzinfo**，绝不能
    astimezone(UTC) 转换（那会把 02:28+08 变成前一天 18:28，误判过期 8 小时）。
    与 customer_membership.py 的 ``replace(tzinfo=timezone.utc)`` 同一处理。
    """
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


class WebTicketError(Exception):
    """票据无效、过期或已被消费。"""


def safe_redirect(value: Optional[str]) -> str:
    """只接受站内绝对路径；拒绝协议相对 URL、反斜杠与控制字符。"""
    if not isinstance(value, str) or not value:
        return DEFAULT_REDIRECT
    candidate = value.strip()
    if not candidate.startswith("/") or candidate.startswith("//") or "\\" in candidate:
        return DEFAULT_REDIRECT
    if any(ord(char) < 32 or ord(char) == 127 for char in candidate):
        return DEFAULT_REDIRECT
    if ":" in candidate.split("?", 1)[0]:
        return DEFAULT_REDIRECT
    return candidate[:512]


def hash_ticket(ticket: str) -> str:
    return hashlib.sha256(ticket.encode("utf-8")).hexdigest()


class WebTicketService:
    @staticmethod
    async def issue(
        *,
        customer_id: int,
        email: Optional[str],
        redirect_to: Optional[str],
        request_id: Optional[str] = None,
    ) -> tuple[str, int]:
        """签发票据；返回 (明文票据, 有效秒数)。"""
        ticket = secrets.token_urlsafe(32)
        now = datetime.utcnow()
        await CustomerWebTicket.create(
            customer_id=customer_id,
            token_hash=hash_ticket(ticket),
            email=email,
            redirect_to=safe_redirect(redirect_to),
            expires_at=now + timedelta(seconds=TICKET_TTL_SECONDS),
            request_id=(request_id or None),
        )
        return ticket, TICKET_TTL_SECONDS

    @staticmethod
    async def exchange(ticket: str) -> CustomerWebTicket:
        """校验并原子消费票据；返回对应票据记录，失败抛 WebTicketError。"""
        if not isinstance(ticket, str) or not (32 <= len(ticket) <= 256):
            raise WebTicketError("invalid")
        record = await CustomerWebTicket.get_or_none(token_hash=hash_ticket(ticket))
        if record is None or record.consumed_at is not None or _naive_utc(record.expires_at) <= datetime.utcnow():
            raise WebTicketError("invalid")
        # CAS：并发重放只有一个请求能把 consumed_at 从 NULL 改成时间。
        updated = await CustomerWebTicket.filter(
            id=record.id, consumed_at__isnull=True,
        ).update(consumed_at=datetime.utcnow())
        if updated != 1:
            raise WebTicketError("replayed")
        return record

    @staticmethod
    async def audit(action: str, customer_id: Optional[int], request, detail: dict) -> None:
        """审计落库；失败仅记日志，不影响登录链路。票据值不得写入 detail。"""
        try:
            from base.common.context import get_current_trace_id
            from base.plugins.audit.models.audit_log import AuditLog

            await AuditLog.create(
                trace_id=get_current_trace_id(),
                user_id=customer_id,
                username=f"cus:{customer_id}" if customer_id is not None else "cus:unknown",
                module="customer",
                operation=action,
                method="POST",
                path="/v1/customer/auth/web-ticket",
                ip_address=(request.client.host if request and request.client else None),
                user_agent=(request.headers.get("user-agent", "")[:500] if request else ""),
                request_params=detail,
                level="info",
            )
        except Exception as exc:
            logger.error(f"[web-ticket] 审计写入失败: {exc}")
