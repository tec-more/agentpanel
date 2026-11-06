"""
会员相关 Schema
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


class MembershipLevelIn(BaseModel):
    """创建/更新会员等级"""
    level_type: str  # regular, vip, svip
    name: str
    description: Optional[str] = None
    duration_days: int = 0  # 0表示无限期
    hours: int = 0  # 套餐包含的充值小时数
    price: Decimal
    discount_percentage: int = 0  # 充值折扣百分比
    features: List[str] = []
    is_active: bool = True


class MembershipLevelOut(BaseModel):
    """会员等级输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    level_type: str
    name: str
    description: Optional[str]
    duration_days: int
    hours: int  # 套餐包含的充值小时数
    price: Decimal
    discount_percentage: int
    features: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerMembershipOut(BaseModel):
    """客户会员信息输出"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    membership_level_id: Optional[int]
    start_time: Optional[datetime]
    expire_time: Optional[datetime]
    total_hours: int
    used_hours: Decimal
    remaining_hours: Decimal
    is_active: bool
    is_vip: bool
    is_svip: bool
    is_expired: bool
    can_get_discount: bool
    discount_percentage: int

    # 包含的会员等级信息
    membership_level: Optional[MembershipLevelOut] = None