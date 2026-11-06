"""
客户会员关系模型
"""

from datetime import datetime
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class CustomerMembership(BaseModel, TimestampMixin):
    """客户会员信息表"""

    customer = fields.OneToOneField(
        "models.Customer",
        related_name="membership",
        on_delete=fields.CASCADE
    )
    membership_level = fields.ForeignKeyField(
        "models.MembershipLevel",
        related_name="customers",
        on_delete=fields.RESTRICT,
        null=True
    )
    start_time = fields.DatetimeField(null=True, description="会员开始时间")
    expire_time = fields.DatetimeField(null=True, description="会员过期时间（null表示无限期）")
    total_hours = fields.IntField(default=0, description="累计充值总小时数")
    level = fields.IntField(default=0, description="Fibonacci动态等级（基于total_hours计算）")
    used_hours = fields.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        description="已使用小时数"
    )
    remaining_hours = fields.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        description="剩余可用小时数"
    )
    is_active = fields.BooleanField(default=True, description="是否激活")
    auto_renew = fields.BooleanField(default=False, description="是否自动续费")

    class Meta:
        table = "customer_membership"

    class Meta:
        table = "customer_membership"
        unique_together = (("customer", "is_active"),)

    @property
    def is_expired(self) -> bool:
        """是否已过期"""
        # 如果没有过期时间，表示无限期（普通会员）
        if not self.expire_time:
            return False

        # 确保 time_zone aware 比较
        from datetime import timezone
        now = datetime.now(timezone.utc)
        # 如果 expire_time 是 naive，视为 UTC 时间
        if self.expire_time.tzinfo is None:
            expire_time = self.expire_time.replace(tzinfo=timezone.utc)
        else:
            expire_time = self.expire_time
        return now > expire_time

    @property
    def is_vip(self) -> bool:
        """是否是VIP或SVIP会员（未过期）"""
        if not self.membership_level:
            return False

        level_type = self.membership_level.level_type
        return self.is_active and not self.is_expired and level_type in ['vip', 'svip']

    @property
    def is_svip(self) -> bool:
        """是否是SVIP会员（未过期）"""
        if not self.membership_level:
            return False

        return self.is_active and not self.is_expired and self.membership_level.level_type == 'svip'

    @property
    def can_get_discount(self) -> bool:
        """是否可以享受充值折扣"""
        return self.is_vip

    @property
    def get_discount_percentage(self) -> int:
        """获取折扣百分比"""
        if not self.membership_level or not self.is_vip:
            return 0

        return self.membership_level.discount_percentage or 0

    def calculate_fibonacci_level(self) -> int:
        """
        根据累计充值总小时数计算Fibonacci动态等级

        计算规则：
        - 累加Fibonacci数列直到超过总小时数
        - level = n，当 sum(F(1) to F(n)) <= total_hours < sum(F(1) to F(n+1))

        示例：
        - 0小时 → Level 0
        - 1小时 → Level 1 (F(1)=1, 累计1)
        - 2小时 → Level 2 (F(1)+F(2)=1+1=2)
        - 3-4小时 → Level 3 (1+1+2=4)
        - 5-7小时 → Level 4 (1+1+2+3=7)
        - 8-12小时 → Level 5 (1+1+2+3+5=12)
        """
        total_hours = self.total_hours or 0

        if total_hours <= 0:
            return 0

        # Fibonacci数列计算
        def get_fibonacci(n: int) -> int:
            if n <= 0:
                return 1
            if n == 1 or n == 2:
                return 1

            a, b = 1, 1
            for _ in range(3, n + 1):
                a, b = b, a + b
            return b

        level = 0
        accumulated_hours = 0

        while True:
            next_hours = get_fibonacci(level + 1)
            if accumulated_hours + next_hours > total_hours:
                break
            accumulated_hours += next_hours
            level += 1

        return level

    def update_fibonacci_level(self):
        """更新Fibonacci动态等级"""
        self.level = self.calculate_fibonacci_level()

    def __str__(self):
        level_name = self.membership_level.name if self.membership_level else "普通会员"
        return f"Customer {self.customer_id} - {level_name} - {self.remaining_hours}h remaining"
