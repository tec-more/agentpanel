"""
会员等级模型
"""

from enum import Enum
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin


class LevelType(str, Enum):
    """会员等级类型"""
    REGULAR = "regular"          # 普通会员（默认，注册即拥有）
    VIP = "vip"                  # VIP会员（付费，享受折扣）
    SVIP = "svip"                # SVIP会员（付费，享受更大折扣）

    @classmethod
    def get_display_name(cls, value):
        """获取等级类型的显示名称"""
        display_names = {
            "regular": "普通会员",
            "vip": "VIP会员",
            "svip": "SVIP会员"
        }
        return display_names.get(str(value), str(value))


class MembershipLevel(BaseModel, TimestampMixin):
    verbose_name = "会员等级"
    """会员等级配置表"""

    level_type = fields.CharEnumField(
        LevelType,
        max_length=20,
        unique=True,
        description="等级类型"
    )
    name = fields.CharField(max_length=50, description="等级名称")
    description = fields.TextField(null=True, description="等级描述")
    duration_days = fields.IntField(default=0, description="有效期天数（0表示无限期）")
    hours = fields.IntField(default=0, description="套餐包含的充值小时数")
    price = fields.DecimalField(max_digits=10, decimal_places=2, description="购买价格")
    discount_percentage = fields.IntField(default=0, description="充值折扣百分比(0-100)")
    features = fields.JSONField(default=list, description="特权列表")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "customer_membership_level"
        ordering = ["id"]

    def get_level_type_display(self):
        """获取等级类型的显示名称（兼容方法）"""
        return LevelType.get_display_name(self.level_type)

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "level_type": self.level_type.value if self.level_type else None,  # 获取Enum的value
            "name": self.name,
            "description": self.description,
            "duration_days": self.duration_days,
            "hours": self.hours,  # 确保包含hours字段
            "price": float(self.price) if self.price else 0,
            "discount_percentage": self.discount_percentage,
            "features": self.features if self.features else [],
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }

    def __str__(self):
        level_type_display = LevelType.get_display_name(self.level_type)
        return f"{self.name} ({level_type_display})"
