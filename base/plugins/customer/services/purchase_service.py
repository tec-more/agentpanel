"""
会员购买和充值折扣服务

处理充值包购买时的折扣计算逻辑
"""

from decimal import Decimal
from typing import Dict, Optional, Tuple
from base.plugins.customer.models.customer_membership import CustomerMembership
from base.plugins.customer.models.membership import MembershipLevel
from base.plugins.customer.models.customer import Customer
class PurchaseService:
    model = "purchase"
    """购买服务 - 处理充值包购买和折扣计算"""

    @staticmethod
    async def calculate_purchase_price(
        customer_id: int,
        original_price: Decimal
    ) -> Tuple[Decimal, int, Optional[MembershipLevel]]:
        """
        计算购买价格（根据会员等级应用折扣）

        Args:
            customer_id: 客户ID
            original_price: 原价

        Returns:
            Tuple[最终价格, 折扣百分比, 会员等级对象]
        """
        # 获取客户会员信息
        membership = await CustomerMembership.get_or_none(
            customer_id=customer_id
        ).prefetch_related("membership_level")

        if not membership or not membership.membership_level:
            # 普通会员，无折扣
            return original_price, 0, None

        level = membership.membership_level

        # 检查会员是否有效
        if membership.is_expired or not membership.is_active:
            # 会员已过期或未激活，无折扣
            return original_price, 0, None

        # 检查是否可以享受折扣
        if not membership.can_get_discount:
            return original_price, 0, level

        # 获取折扣百分比
        discount_percentage = membership.get_discount_percentage

        if discount_percentage <= 0:
            return original_price, 0, level

        # 计算折扣后价格
        discount_amount = original_price * Decimal(discount_percentage) / Decimal(100)
        final_price = original_price - discount_amount

        # 确保价格不为负数
        if final_price < 0:
            final_price = Decimal(0)

        return final_price, discount_percentage, level

    @staticmethod
    def format_price_display(
        original_price: Decimal,
        final_price: Decimal,
        discount_percentage: int
    ) -> Dict:
        """
        格式化价格显示信息

        Returns:
            {
                "original_price": "¥199.00",
                "final_price": "¥179.10",
                "discount_percentage": 10,
                "save_amount": "¥19.90",
                "has_discount": true
            }
        """
        has_discount = discount_percentage > 0 and original_price > final_price

        return {
            "original_price": f"¥{original_price:.2f}",
            "final_price": f"¥{final_price:.2f}",
            "discount_percentage": discount_percentage,
            "save_amount": f"¥{original_price - final_price:.2f}" if has_discount else "¥0.00",
            "has_discount": has_discount,
            "discount_text": f"{discount_percentage}% OFF" if has_discount else ""
        }

    @staticmethod
    async def get_customer_membership_info(customer_id: int) -> Optional[Dict]:
        """
        获取客户会员信息（用于前端显示）

        Returns:
            {
                "level_type": "vip",
                "level_name": "VIP会员",
                "is_vip": true,
                "is_svip": false,
                "is_expired": false,
                "discount_percentage": 10,
                "expire_time": "2027-03-29 10:00:00",
                "total_hours": 100,
                "remaining_hours": 50.5
            }
        """
        membership = await CustomerMembership.get_or_none(
            customer_id=customer_id
        ).prefetch_related("membership_level")

        if not membership:
            # 返回默认普通会员信息
            return {
                "level_type": "regular",
                "level_name": "普通会员",
                "is_vip": False,
                "is_svip": False,
                "is_expired": False,
                "discount_percentage": 0,
                "expire_time": None,
                "total_hours": 0,
                "remaining_hours": 0,
                "can_get_discount": False
            }

        level = membership.membership_level

        return {
            "level_type": level.level_type if level else "regular",
            "level_name": level.name if level else "普通会员",
            "is_vip": membership.is_vip,
            "is_svip": membership.is_svip,
            "is_expired": membership.is_expired,
            "discount_percentage": membership.get_discount_percentage,
            "can_get_discount": membership.can_get_discount,
            "expire_time": membership.expire_time.isoformat() if membership.expire_time else None,
            "total_hours": membership.total_hours,
            "remaining_hours": float(membership.remaining_hours)
        }

    @staticmethod
    async def validate_purchase_permission(
        customer_id: int
    ) -> Tuple[bool, str]:
        """
        验证客户是否可以购买

        Returns:
            Tuple[是否可以购买, 错误消息]
        """
        from base.plugins.customer.models.customer import Customer

        customer = await Customer.get_or_none(id=customer_id)
        if not customer:
            return False, "客户不存在"

        if not customer.is_active:
            return False, "客户已被禁用"

        return True, ""

    @staticmethod
    def get_level_benefits(level_type: str) -> Dict:
        """
        获取会员等级权益说明

        Returns:
            {
                "name": "VIP会员",
                "description": "365天有效期，充值享受9折优惠",
                "benefits": ["基础功能", "正常使用", "优先客服", "充值9折"],
                "discount_text": "充值享受9折优惠"
            }
        """
        benefits_map = {
            "regular": {
                "name": "普通会员",
                "description": "注册即拥有，无限期，购买充值包无折扣",
                "benefits": ["基础功能", "正常使用"],
                "discount_text": "购买充值包无折扣",
                "color": "#909399",
                "badge_type": "info"
            },
            "vip": {
                "name": "VIP会员",
                "description": "付费会员，365天有效期，充值享受9折优惠",
                "benefits": ["基础功能", "正常使用", "优先客服", "充值9折"],
                "discount_text": "充值享受9折优惠",
                "color": "#F56C6C",
                "badge_type": "danger"
            },
            "svip": {
                "name": "SVIP会员",
                "description": "超级会员，365天有效期，充值享受8折优惠",
                "benefits": ["基础功能", "正常使用", "专属客服", "充值8折", "无限翻译"],
                "discount_text": "充值享受8折优惠",
                "color": "#FFC107",
                "badge_type": "warning"
            }
        }

        return benefits_map.get(level_type, benefits_map["regular"])


# 导出单例
purchase_service = PurchaseService()
