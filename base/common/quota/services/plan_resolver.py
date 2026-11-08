"""L2 套餐解析器：客户会员等级 / 用户激活角色（ORM 版）。

P3 D-P3-2=B：共享 `plan_service` 只保留解析骨架，环境相关的两次读取由入口注入。
本文件是 L2 的注入实现（`services/l3-gateway/app/plan_resolver.py` 为网关注入的只读 SQL 版），
两份实现必须由 `services/l3-gateway/tests/plan_parity.py` 逐字段对拍。

语义冻结（spec §13.6）：
- cus：CustomerMembership.filter(customer_id, is_active=True).select_related(membership_level).first()
  - 无记录 / is_expired / 等级缺失 → "regular"；异常 → None
- usr：User.get_or_none(id).prefetch_related(roles)，取 is_active 角色 code；异常 → []
"""
from typing import List, Optional

from loguru import logger


class L2PlanResolver:
    async def customer_level_type(self, customer_id: int) -> Optional[str]:
        try:
            from base.plugins.customer.models.customer_membership import CustomerMembership

            membership = await CustomerMembership.filter(
                customer_id=customer_id, is_active=True
            ).select_related("membership_level").first()
            if membership is None:
                return "regular"
            if membership.is_expired:
                return "regular"
            if membership.membership_level and membership.membership_level.level_type:
                level_type = membership.membership_level.level_type
                return getattr(level_type, "value", level_type)
            return "regular"
        except Exception as e:
            logger.warning(f"[quota] 解析客户会员等级失败 customer_id={customer_id}: {e}")
            return None

    async def user_role_codes(self, user_id: int) -> List[str]:
        try:
            from base.core.users.models.users import User

            user = await User.get_or_none(id=user_id).prefetch_related("roles")
            if user is None:
                return []
            return [r.code for r in user.roles if r.is_active]
        except Exception as e:
            logger.warning(f"[quota] 解析用户角色失败 user_id={user_id}: {e}")
            return []
