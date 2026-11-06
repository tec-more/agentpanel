"""
IdentityLink model - 客户与后台用户的身份关联（L1 关联，Q8）

溯源：docs/arch/02-系统上下文与领域模型.md §4.2；PRD §3.2/§3.3
- 替代 customer.system_user_id 语义（旧列保留只读，Q-C 存量迁入本表）
- 关联仅允许"提示→主动确认→验证"流程建立（R-14），禁止任何自动绑定代码路径
- 一个自然人最多关联 1 个客户主体与 1 个后台主体（D1），双列各自唯一
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class IdentityLink(BaseModel, TimestampMixin):
    verbose_name = "身份关联"
    """Identity link between Customer and User (L1)"""

    # D1：映射关系唯一，双列各自 UNIQUE
    customer = fields.ForeignKeyField(
        "models.Customer",
        related_name="identity_link",
        on_delete=fields.CASCADE,
        unique=True,
        description="客户主体（唯一）",
    )
    user = fields.ForeignKeyField(
        "models.User",
        related_name="identity_link",
        on_delete=fields.CASCADE,
        unique=True,
        description="后台用户主体（唯一）",
    )

    # 状态机：prompted(已提示待确认) / linked(已关联) / dismissed(不再提示)
    status = fields.CharField(
        max_length=20, default="prompted", description="状态: prompted/linked/dismissed"
    )
    # L9：解绑冷却期截止；L7 提示频率控制由服务层结合 audit 实现
    dismissed_until = fields.DatetimeField(null=True, description="不再提示/冷却期截止时间")

    # 验证信息（L5/L6）：password=对方密码验证, email_code=邮箱验证码
    verified_via = fields.CharField(max_length=20, null=True, description="验证方式: password/email_code")
    verified_at = fields.DatetimeField(null=True, description="验证通过时间")

    # L10 审计：提示/跳过/不再提示/发起/失败/成功/解绑 事件流水（JSON 数组追加）
    audit = fields.JSONField(null=True, description="关联过程审计事件列表")

    class Meta:
        table = "identity_link"

    def __str__(self):
        return f"IdentityLink(customer_id={self.customer_id}, user_id={self.user_id}, status={self.status})"
