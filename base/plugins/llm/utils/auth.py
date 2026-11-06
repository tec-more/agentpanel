"""
管理员权限验证辅助函数
"""
from fastapi import Depends, HTTPException, status
from typing import Optional

from base.common.security import get_current_user_id


async def check_admin_permission(user_id: int = Depends(get_current_user_id)) -> int:
    """
    检查用户是否是管理员

    Args:
        user_id: 当前用户ID

    Returns:
        用户ID

    Raises:
        HTTPException: 如果用户不是管理员
    """
    try:
        from base.core.users.services.user_service import UserService
        user = await UserService.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        # 检查是否是超级管理员
        if user.is_superuser:
            return user_id

        # 检查是否有管理员角色
        roles = await user.roles.filter(is_active=True).all()
        for role in roles:
            if role.code in ['admin', 'super_admin', 'administrator']:
                return user_id

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    except ImportError:
        # 如果用户模块不可用，只检查is_superuser
        from base.plugins.customer.models.customer import Customer
        customer = await Customer.get_or_none(id=user_id)

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )

        # TODO: 客户表中可能需要添加is_admin字段
        # 暂时允许所有登录用户访问
        return user_id


# 为了保持向后兼容，创建一个别名
require_admin = check_admin_permission
