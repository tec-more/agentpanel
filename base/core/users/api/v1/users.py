"""
用户管理API
"""
from fastapi import APIRouter, Depends, status, Query
from typing import Optional

from base.core.users.schemas.users import (
    UserResponse,
    UserCreate,
    UserUpdate,
    UserListQuery,
    UserListResponse,
)
from base.core.users.services.user_service import UserService
from base.common.security import get_current_user_id
from base.common.response import SuccessResponse, ErrorResponse

router = APIRouter(prefix="/v1/users", tags=["用户管理"])


@router.get("/list", summary="获取用户列表(分页)")
async def get_user_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=200, description="每页数量"),
        username: Optional[str] = Query(None, description="用户名(模糊搜索)"),
        email: Optional[str] = Query(None, description="邮箱(模糊搜索)"),
        is_active: Optional[bool] = Query(None, description="是否激活"),
        dept_id: Optional[int] = Query(None, description="部门ID"),
        current_user_id: int = Depends(get_current_user_id)
):
    """
    获取用户列表(分页)

    需要认证

    Args:
        page: 页码
        page_size: 每页数量
        username: 用户名(模糊搜索)
        email: 邮箱(模糊搜索)
        is_active: 是否激活
        dept_id: 部门ID
        current_user_id: 当前用户ID

    Returns:
        用户列表
    """
    users, total = await UserService.get_user_list(
        page=page,
        page_size=page_size,
        username=username,
        email=email,
        is_active=is_active,
        dept_id=dept_id,
    )

    # 转换为字典列表
    user_list = []
    for user in users:
        user_dict = await user.to_dict()
        user_list.append(user_dict)

    response_data = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": user_list
    }

    return SuccessResponse(data=response_data)


@router.get("/{user_id}", summary="获取用户详情")
async def get_user_detail(
        user_id: int,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    获取用户详情

    Args:
        user_id: 用户ID
        current_user_id: 当前用户ID

    Returns:
        用户详细信息
    """
    user = await UserService.get_by_id(user_id)
    if not user:
        return ErrorResponse(
            msg="用户不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    user_dict = await user.to_dict()
    return SuccessResponse(data=user_dict)


@router.post("", summary="创建用户")
async def create_user(
        user_data: UserCreate,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    创建新用户(管理员功能)

    Args:
        user_data: 用户创建数据
        current_user_id: 当前用户ID

    Returns:
        创建的用户信息
    """
    # 检查当前用户是否是管理员(后续可以加权限验证)
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # 检查用户名是否存在
    if await UserService.check_username_exists(user_data.username):
        return ErrorResponse(
            msg="用户名已存在",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # 检查邮箱是否存在
    if await UserService.check_email_exists(user_data.email):
        return ErrorResponse(
            msg="邮箱已被注册",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # 创建用户
    user = await UserService.create_user(user_data)
    user_dict = await user.to_dict()

    return SuccessResponse(data=user_dict, msg="创建成功")


@router.put("/{user_id}", summary="更新用户信息")
async def update_user(
        user_id: int,
        user_data: UserUpdate,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    更新用户信息

    Args:
        user_id: 用户ID
        user_data: 更新数据
        current_user_id: 当前用户ID

    Returns:
        更新后的用户信息
    """
    # 检查当前用户是否有权限(只能修改自己或管理员可以修改所有人)
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user:
        return ErrorResponse(
            msg="当前用户不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    # 非管理员只能修改自己的信息
    if user_id != current_user_id and not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限修改其他用户信息",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # 检查邮箱是否被其他用户使用
    if user_data.email:
        if await UserService.check_email_exists(user_data.email, exclude_id=user_id):
            return ErrorResponse(
                msg="邮箱已被其他用户使用",
                status_code=status.HTTP_400_BAD_REQUEST
            )

    # 更新用户
    user = await UserService.update_user(user_id, user_data)
    if not user:
        return ErrorResponse(
            msg="用户不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    user_dict = await user.to_dict()
    return SuccessResponse(data=user_dict, msg="更新成功")


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
        user_id: int,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    删除用户(管理员功能)

    Args:
        user_id: 用户ID
        current_user_id: 当前用户ID

    Returns:
        删除结果
    """
    # 检查当前用户是否是管理员
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # 不能删除自己
    if user_id == current_user_id:
        return ErrorResponse(
            msg="不能删除自己",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # 删除用户
    success = await UserService.delete_user(user_id)
    if not success:
        return ErrorResponse(
            msg="用户不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    return SuccessResponse(msg="删除成功")


@router.patch("/{user_id}/toggle-status", summary="切换用户状态")
async def toggle_user_status(
        user_id: int,
        current_user_id: int = Depends(get_current_user_id)
):
    """
    切换用户激活状态(管理员功能)

    Args:
        user_id: 用户ID
        current_user_id: 当前用户ID

    Returns:
        更新后的用户信息
    """
    # 检查当前用户是否是管理员
    current_user = await UserService.get_by_id(current_user_id)
    if not current_user or not current_user.is_superuser:
        return ErrorResponse(
            msg="无权限执行此操作",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # 获取目标用户
    user = await UserService.get_by_id(user_id)
    if not user:
        return ErrorResponse(
            msg="用户不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    # 不能禁用自己
    if user_id == current_user_id:
        return ErrorResponse(
            msg="不能禁用自己",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # 切换状态
    user_update = UserUpdate(is_active=not user.is_active)
    updated_user = await UserService.update_user(user_id, user_update)

    user_dict = await updated_user.to_dict()
    status_text = "激活" if updated_user.is_active else "禁用"
    return SuccessResponse(data=user_dict, msg=f"用户已{status_text}")
