"""
配额预占持久化 - QuotaReservation

溯源：
- docs/arch/03 §3.6 事实源/对账/崩溃恢复
- docs/arch/05 §1.1 Redis 降级、§1.2 幂等
- Harness P0：预占不能只存 Redis/进程内存，必须落库；hold_id 必须由调用方显式传入，
  禁止再用 str(execution_id) 作为 hold_id（同一执行多步会互相覆盖）。
"""
from tortoise import fields

from packages.agentpanel_common.models.base import BaseModel, TimestampMixin


class QuotaReservation(BaseModel, TimestampMixin):
    """预占登记（对账事实源）

    items        : 当前剩余预占量 {配额项: 数量}
    original_items: 初次预占量（对账用）
    used_items   : 已结算消耗量（由预占转正式的部分）
    status       : active / partial / settled / released / expired
    """

    hold_id = fields.CharField(max_length=128, unique=True, index=True, description="预占唯一键")
    owner_type = fields.CharField(max_length=3, description="主体类型: cus/usr/org")
    owner_id = fields.BigIntField(description="主体 ID")
    plan_id = fields.BigIntField(null=True, description="预占时套餐 ID")
    period = fields.CharField(max_length=10, default="", description="周期标识（月/日）")
    items = fields.JSONField(default=dict, description="剩余预占量")
    original_items = fields.JSONField(default=dict, description="初次预占量")
    used_items = fields.JSONField(default=dict, description="已结算量")
    status = fields.CharField(max_length=20, default="active", description="状态")
    # 计数事实源模式：redis=实时计数（account.used 为对账落盘值）；db=Redis 降级时已预扣 used
    counter_mode = fields.CharField(max_length=10, default="redis", description="计数模式: redis/db")
    source = fields.CharField(max_length=30, default="agent", description="来源: agent/harness/other")
    ref_type = fields.CharField(max_length=50, null=True, description="业务对象类型")
    ref_id = fields.CharField(max_length=128, null=True, index=True, description="业务对象 ID")
    execution_id = fields.BigIntField(null=True, index=True, description="关联执行实例（兼容旧调用）")
    expire_at = fields.DatetimeField(null=True, description="预占过期时间")
    settled_at = fields.DatetimeField(null=True, description="结算完成时间")
    released_at = fields.DatetimeField(null=True, description="释放时间")
    meta = fields.JSONField(null=True, description="扩展信息")

    class Meta:
        table = "quota_reservation"
        table_description = "配额预占登记表"
        indexes = [
            ("owner_type", "owner_id", "status"),
            ("status", "expire_at"),
        ]

    def __str__(self):
        return f"QuotaReservation({self.hold_id}, {self.status})"
