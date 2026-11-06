"""
临时修复VIP状态的API端点
"""
from fastapi import APIRouter, HTTPException
from base.common.response import SuccessResponse, ErrorResponse

fix_vip_router = APIRouter(
    prefix="/fix-vip",
    tags=["临时修复VIP"]
)

@fix_vip_router.post("/{customer_id}", summary="修复用户VIP状态（临时）")
async def fix_user_vip_status(customer_id: int):
    """
    手动修复用户的VIP状态

    将用户的会员等级升级为VIP，并设置过期时间

    Args:
        customer_id: 客户ID

    Returns:
        修复结果
    """
    from base.plugins.customer.models.customer_membership import CustomerMembership
    from base.plugins.customer.models.membership import MembershipLevel
    from datetime import datetime, timedelta, timezone

    try:
        # 查询用户会员信息
        membership = await CustomerMembership.get_or_none(
            customer_id=customer_id
        ).prefetch_related("membership_level")

        if not membership:
            return ErrorResponse(msg=f"用户{customer_id}没有会员记录", status_code=404)

        # 获取VIP会员等级
        vip_level = await MembershipLevel.filter(
            level_type="vip"
        ).first()

        if not vip_level:
            return ErrorResponse(msg="VIP会员等级不存在", status_code=400)

        # 修复前状态
        old_level_type = membership.membership_level.level_type if membership.membership_level else "None"
        old_is_vip = membership.is_vip

        # 更新会员等级为VIP
        membership.membership_level_id = vip_level.id

        # 设置过期时间（VIP有30天有效期）
        now = datetime.now(timezone.utc)
        membership.start_time = now
        membership.expire_time = now + timedelta(days=vip_level.duration_days)

        await membership.save()

        # 重新查询验证
        await membership.fetch_related("membership_level")
        new_level_type = membership.membership_level.level_type
        new_is_vip = membership.is_vip

        return SuccessResponse(data={
            "customer_id": customer_id,
            "fix_applied": True,
            "before": {
                "level_type": old_level_type,
                "is_vip": old_is_vip
            },
            "after": {
                "level_type": new_level_type,
                "is_vip": new_is_vip,
                "membership_level_id": membership.membership_level_id,
                "expire_time": membership.expire_time.isoformat() if membership.expire_time else None
            }
        }, msg="VIP状态修复成功")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return ErrorResponse(msg=f"修复失败: {str(e)}", status_code=500)
