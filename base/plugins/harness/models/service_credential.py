"""服务间凭据（L3 编排内部 API 认证）

- 明文密钥只由部署环境注入，库中只存 SHA-256 哈希；
- L2 负责签发/吊销（后续阶段），L3 只读校验；
- 与 HarnessClient（客户端凭据）完全分离，互不复用。
"""
from tortoise import fields

from base.common.model import BaseModel, TimestampMixin


class ServiceCredential(BaseModel, TimestampMixin):
    service_id = fields.CharField(max_length=64, unique=True, index=True, description="服务标识")
    secret_hash = fields.CharField(max_length=128, description="密钥 SHA-256（小写十六进制）")
    scopes = fields.JSONField(default=list, description="授权范围")
    description = fields.TextField(null=True, description="备注")
    status = fields.CharField(max_length=20, default="active", description="active/disabled/revoked")
    expires_at = fields.DatetimeField(null=True, description="过期时间")

    class Meta:
        table = "service_credential"
        table_description = "服务间凭据表"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ServiceCredential({self.service_id})"
