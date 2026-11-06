"""
QuotaPlanBinding 模型 - M9 套餐绑定关系（Q-D 双向映射）

溯源：docs/arch/02 §4.2「MembershipLevel/Role → QuotaPlan 单向映射」；
quota.py QuotaPlan docstring「映射关系由服务层维护，不在本表建 FK」（T1 预留）。

- bind_type=membership_level：bind_key 取 MembershipLevel.level_type（regular/vip/svip）
- bind_type=role：bind_key 取 Role.code
- priority：同主体命中多条绑定时取优先级最高者（数值大者优先），并列取 plan_id 大者
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class QuotaPlanBinding(BaseModel, TimestampMixin):
    verbose_name = "套餐绑定"
    """Binding between membership level / role and quota plan"""

    BIND_TYPE_MEMBERSHIP_LEVEL = "membership_level"
    BIND_TYPE_ROLE = "role"

    bind_type = fields.CharField(
        max_length=30, description="绑定类型: membership_level/role"
    )
    bind_key = fields.CharField(
        max_length=50, description="绑定键: 会员等级 level_type 或角色 code"
    )
    plan = fields.ForeignKeyField(
        "models.QuotaPlan",
        related_name="bindings",
        on_delete=fields.CASCADE,
        description="绑定套餐",
    )
    priority = fields.IntField(default=0, description="优先级（数值大者优先）")

    class Meta:
        table = "quota_plan_binding"
        unique_together = (("bind_type", "bind_key"),)

    def __str__(self):
        return f"QuotaPlanBinding({self.bind_type}:{self.bind_key} -> plan {self.plan_id})"
