"""一次性 Web 登录票据（dsh → 客户门户免登）。

只存票据哈希：明文仅出现在签发响应与门户 URL 中，且 60 秒后失效。
"""
from tortoise import fields

from base.common.model import BaseModel, TimestampMixin


class CustomerWebTicket(BaseModel, TimestampMixin):
    customer_id = fields.BigIntField(description="客户主体 ID")
    token_hash = fields.CharField(max_length=64, unique=True, description="票据 SHA-256（不存明文）")
    email = fields.CharField(max_length=255, null=True, description="签发时的客户邮箱（审计用）")
    redirect_to = fields.CharField(max_length=512, default="/dashboard", description="站内跳转路径")
    expires_at = fields.DatetimeField(description="过期时间（UTC naive）")
    consumed_at = fields.DatetimeField(null=True, description="消费时间；非 NULL 即已使用")
    request_id = fields.CharField(max_length=64, null=True, description="签发请求的 trace id")

    class Meta:
        table = "customer_web_ticket"
        table_description = "客户门户一次性登录票据"
