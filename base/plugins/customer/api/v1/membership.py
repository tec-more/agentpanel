"""
会员相关 API
"""

from fastapi import APIRouter, Depends, Query, Body
from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal
from base.common.response import success_response, fail_response
from base.plugins.customer.schemas import (
    MembershipLevelOut,
    MembershipLevelIn,
    CustomerMembershipOut
)
from base.plugins.customer.services.membership_service import MembershipService
from base.plugins.customer.services.purchase_service import purchase_service
from base.core.users.models.users import User
from base.common.security import get_current_user

membership_router = APIRouter(prefix="/membership", tags=["客户会员"])


class CalculatePriceIn(BaseModel):
    """计算价格输入"""
    customer_id: int
    original_price: Decimal


class CalculatePriceOut(BaseModel):
    """计算价格输出"""
    original_price: str
    final_price: str
    discount_percentage: int
    save_amount: str
    has_discount: bool
    discount_text: str
    level_info: Optional[dict] = None


async def get_or_create_customer(user: User) -> "Customer":
    """
    获取或创建客户记录

    RK-14/R-14：已移除按 system_user_id 自动关联的写入路径（旧列只读废弃，
    身份关联迁移至 identity_link，仅可经 /identity 提示→确认→验证流程建立）。
    此处仅按邮箱定位/创建客户主体本身，不建立任何跨主体映射。
    """
    from base.plugins.customer.models.customer import Customer
    from base.plugins.customer.services.membership_service import MembershipService

    # 仅通过 email 查找（不再读写 system_user_id）
    customer = await Customer.get_or_none(email=user.email)

    if not customer:
        # 创建新的客户记录（不携带任何跨主体关联字段）
        customer = await Customer.create(
            username=user.username,
            email=user.email,
            nickname=getattr(user, "nickname", None),
            avatar=getattr(user, "avatar", None),
            is_active=True
        )

        # 🎁 新用户注册时自动赠送普通会员
        try:
            await MembershipService.initialize_regular_member(customer.id)
            print(f"[Membership] ✅ 新用户 {customer.username} 已自动初始化为普通会员")
        except Exception as e:
            print(f"[Membership] ⚠️  初始化普通会员失败: {e}")
            # 不影响用户注册流程
    else:
        # 检查是否已经有会员记录，如果没有则创建
        from base.plugins.customer.models.customer_membership import CustomerMembership
        existing_membership = await CustomerMembership.get_or_none(customer_id=customer.id)
        if not existing_membership:
            try:
                await MembershipService.initialize_regular_member(customer.id)
                print(f"[Membership] ✅ 为老用户 {customer.username} 补充创建普通会员记录")
            except Exception as e:
                print(f"[Membership] ⚠️  补充创建普通会员失败: {e}")

    return customer


@membership_router.get("/levels", summary="获取会员等级列表")
async def get_membership_levels(
    active_only: bool = True
):
    """
    获取所有可用的会员等级

    返回：普通会员、VIP会员、SVIP会员
    """
    levels = await MembershipService.get_all_levels(active_only=active_only)
    return success_response(data=levels)


@membership_router.get("/my-level", summary="获取我的会员等级")
async def get_my_membership_level(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户的会员等级信息

    包含：
    - 会员等级类型（普通/VIP/SVIP）
    - 是否可享受折扣
    - 过期时间
    - 充值总小时数
    - 剩余小时数
    """
    customer = await get_or_create_customer(current_user)
    membership_info = await purchase_service.get_customer_membership_info(customer.id)

    return success_response(data=membership_info)


@membership_router.post("/calculate-price", summary="计算购买价格（应用会员折扣）")
async def calculate_purchase_price(
    request_data: CalculatePriceIn,
    current_user: User = Depends(get_current_user)
):
    """
    计算充值包购买价格（根据会员等级应用折扣）

    请求示例：
    ```json
    {
        "customer_id": 123,
        "original_price": 99.00
    }
    ```

    返回示例：
    ```json
    {
        "original_price": "¥99.00",
        "final_price": "¥89.10",
        "discount_percentage": 10,
        "save_amount": "¥9.90",
        "has_discount": true,
        "discount_text": "10% OFF",
        "level_info": {
            "level_type": "vip",
            "level_name": "VIP会员",
            "discount_percentage": 10
        }
    }
    ```
    """
    final_price, discount_percentage, level = await purchase_service.calculate_purchase_price(
        request_data.customer_id,
        request_data.original_price
    )

    price_display = purchase_service.format_price_display(
        request_data.original_price,
        final_price,
        discount_percentage
    )

    # 添加会员等级信息
    level_info = None
    if level:
        level_info = {
            "level_type": level.level_type,
            "level_name": level.name,
            "discount_percentage": level.discount_percentage
        }

    return success_response(data={
        **price_display,
        "level_info": level_info
    })


@membership_router.get("/level-benefits/{level_type}", summary="获取会员等级权益")
async def get_level_benefits(
    level_type: str
):
    """
    获取指定会员等级的权益说明

    支持的等级类型：regular, vip, svip
    """
    benefits = purchase_service.get_level_benefits(level_type)
    return success_response(data=benefits)


@membership_router.post("/levels", summary="创建会员等级")
async def create_membership_level(
    level_data: MembershipLevelIn,
    current_user: User = Depends(get_current_user)
):
    """
    创建会员等级

    管理员功能
    """
    try:
        # 将 Pydantic 模型转换为字典
        level_dict = level_data.model_dump()

        level = await MembershipService.create_level(level_dict)

        # 转换为字典确保datetime字段被正确格式化
        if hasattr(level, 'to_dict'):
            level_dict = await level.to_dict()
        elif hasattr(level, 'dict'):
            level_dict = level.dict()
        else:
            level_dict = dict(level)

        return success_response(data=level_dict, msg="会员等级创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@membership_router.put("/levels/{level_id}", summary="更新会员等级")
async def update_membership_level(
    level_id: int,
    level_data: MembershipLevelIn,
    current_user: User = Depends(get_current_user)
):
    """
    更新会员等级

    管理员功能
    """
    try:
        # 将 Pydantic 模型转换为字典
        update_dict = level_data.model_dump(exclude_unset=True)

        level = await MembershipService.update_level(level_id, update_dict)

        if not level:
            return fail_response(msg="会员等级不存在")

        # 转换为字典确保datetime字段被正确格式化
        if hasattr(level, 'to_dict'):
            level_dict = await level.to_dict()
        elif hasattr(level, 'dict'):
            level_dict = level.dict()
        else:
            level_dict = dict(level)

        return success_response(data=level_dict, msg="会员等级更新成功")
    except Exception as e:
        return fail_response(msg=str(e))


@membership_router.delete("/levels/{level_id}", summary="删除会员等级")
async def delete_membership_level(
    level_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    删除会员等级

    管理员功能
    """
    try:
        success = await MembershipService.delete_level(level_id)
        if not success:
            return fail_response(msg="会员等级不存在")
        return success_response(msg="会员等级删除成功")
    except Exception as e:
        return fail_response(msg=str(e))


@membership_router.patch("/levels/{level_id}", summary="切换会员等级状态")
async def toggle_membership_level_status(
    level_id: int,
    status_data: dict = None,
    current_user: User = Depends(get_current_user)
):
    """
    切换会员等级启用状态

    管理员功能
    """
    try:
        if status_data is None:
            status_data = {}

        is_active = status_data.get("is_active", True)
        level = await MembershipService.update_level(level_id, {"is_active": is_active})

        if not level:
            return fail_response(msg="会员等级不存在")

        # 转换为字典确保datetime字段被正确格式化
        if hasattr(level, 'to_dict'):
            level_dict = await level.to_dict()
        elif hasattr(level, 'dict'):
            level_dict = level.dict()
        else:
            level_dict = dict(level)

        status_text = "启用" if is_active else "禁用"
        return success_response(data=level_dict, msg=f"会员等级已{status_text}")
    except Exception as e:
        return fail_response(msg=str(e))
