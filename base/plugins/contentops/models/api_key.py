"""ContentOps 对外 OpenAPI 专属 API Key 模型（M4）。

安全约定（对齐 harness client / gateway 虚拟 key）：
- secret 明文只在签发响应回显一次，DB 只存 SHA-256；
- 绑定 CUS 租户归属（owner_type/owner_id），外部调用只能访问该租户可见的规则/内容；
- scope 白名单限定只读能力，status 支持 active/disabled/revoked；
- allowed_ips 白名单、expires_at 过期、rate_limit_rpm 限流。
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class ContentopsApiKey(BaseModel, TimestampMixin):
    """对外 OpenAPI 凭据。secret 只存哈希，明文仅签发时回显一次。"""
    key_id = fields.CharField(max_length=64, unique=True, index=True, description="Key ID（公开标识）")
    name = fields.CharField(max_length=100, description="Key 名称")
    secret_hash = fields.CharField(max_length=128, description="secret SHA-256")
    secret_prefix = fields.CharField(max_length=24, default="", description="secret 前缀（展示用）")
    status = fields.CharField(max_length=20, default="active", description="active/disabled/revoked")
    scopes = fields.JSONField(default=list, description="授权范围白名单")

    # 绑定 CUS 租户：外部调用继承该归属，仅可见平台级 + 本租户规则
    owner_type = fields.CharField(max_length=3, default="cus", description="归属主体类型（默认 cus）")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID（customer.id）")

    allowed_ips = fields.JSONField(null=True, description="IP 白名单（空=不限）")
    expires_at = fields.DatetimeField(null=True, description="过期时间")
    rate_limit_rpm = fields.IntField(default=60, description="每分钟请求上限（0=不限）")
    rate_window_started = fields.DatetimeField(null=True, description="限流窗口起点")
    rate_window_count = fields.IntField(default=0, description="当前窗口计数")
    last_used_at = fields.DatetimeField(null=True, description="最近使用时间")
    revoked_at = fields.DatetimeField(null=True, description="吊销时间")
    created_by = fields.BigIntField(null=True, description="创建人（员工/客户 ID）")
    description = fields.TextField(null=True, description="备注")

    class Meta:
        table = "contentops_api_key"
        indexes = [("owner_type", "owner_id"), ("status",)]
