"""
仪表盘API
"""
from fastapi import APIRouter, Depends
from base.common.response import SuccessResponse
from base.common.security import get_current_user
from base.core.users.models.users import User
from base.core.users.models.rbac import Role, Permission, Menu
from base.core.dept.models.department import Department

router = APIRouter(prefix="/v1/dashboard", tags=["仪表盘"])


@router.get("/stats", summary="获取仪表盘统计数据")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    """获取仪表盘统计数据"""
    # 获取各项统计数据
    user_count = await User.all().count()
    active_user_count = await User.filter(is_active=True).count()
    dept_count = await Department.all().count()
    role_count = await Role.filter(is_active=True).count()
    permission_count = await Permission.filter(is_active=True).count()
    menu_count = await Menu.filter(is_active=True).count()

    # 获取最近注册的用户
    recent_users = await User.all().order_by('-created_at').limit(5)
    recent_users_data = []
    for user in recent_users:
        recent_users_data.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else None
        })

    return SuccessResponse(data={
        "user_count": user_count,
        "active_user_count": active_user_count,
        "dept_count": dept_count,
        "role_count": role_count,
        "permission_count": permission_count,
        "menu_count": menu_count,
        "recent_users": recent_users_data
    })


@router.get("/user-info", summary="获取当前用户信息")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的详细信息"""
    # 获取用户角色
    roles = await current_user.roles.filter(is_active=True).all()
    role_names = [role.name for role in roles]

    return SuccessResponse(data={
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "alias": current_user.alias,
        "is_superuser": current_user.is_superuser,
        "is_active": current_user.is_active,
        "roles": role_names,
        "created_at": current_user.created_at.strftime("%Y-%m-%d %H:%M") if current_user.created_at else None,
        "last_login": current_user.last_login.strftime("%Y-%m-%d %H:%M") if current_user.last_login else None
    })
