"""
用户服务层
"""
from typing import Optional, List, Tuple
from datetime import datetime
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from base.core.users.models.users import User
from base.core.users.schemas.users import UserCreate, UserUpdate
from base.common.security import get_password_hash, verify_password


class UserService:
    """用户服务类"""

    @staticmethod
    async def get_by_id(user_id: int) -> Optional[User]:
        """
        根据ID获取用户

        Args:
            user_id: 用户ID

        Returns:
            Optional[User]: 用户对象,不存在返回None
        """
        return await User.filter(id=user_id).first()

    @staticmethod
    async def get_by_username(username: str) -> Optional[User]:
        """
        根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            Optional[User]: 用户对象,不存在返回None
        """
        return await User.filter(username=username).first()

    @staticmethod
    async def get_by_email(email: str) -> Optional[User]:
        """
        根据邮箱获取用户

        Args:
            email: 邮箱

        Returns:
            Optional[User]: 用户对象,不存在返回None
        """
        return await User.filter(email=email).first()

    @staticmethod
    async def create_user(user_data: UserCreate) -> User:
        """
        创建用户

        Args:
            user_data: 用户创建数据

        Returns:
            User: 创建的用户对象
        """
        # 密码加密
        hashed_password = get_password_hash(user_data.password)

        # 创建用户
        user = await User.create(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            alias=user_data.alias,
            phone=user_data.phone,
            dept_id=user_data.dept_id,
        )
        return user

    @staticmethod
    async def update_user(user_id: int, user_data: UserUpdate) -> Optional[User]:
        """
        更新用户

        Args:
            user_id: 用户ID
            user_data: 更新数据

        Returns:
            Optional[User]: 更新后的用户对象
        """
        user = await User.filter(id=user_id).first()
        if not user:
            return None

        # 只更新提供的字段
        update_data = user_data.model_dump(exclude_unset=True)
        await user.update_from_dict(update_data).save()
        return user

    @staticmethod
    async def delete_user(user_id: int) -> bool:
        """
        删除用户

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否删除成功
        """
        deleted_count = await User.filter(id=user_id).delete()
        return deleted_count > 0

    @staticmethod
    async def authenticate(username_or_email: str, password: str) -> Optional[User]:
        """
        用户认证（支持用户名或邮箱）

        Args:
            username_or_email: 用户名或邮箱
            password: 密码

        Returns:
            Optional[User]: 认证成功返回用户对象,失败返回None
        """
        # 先尝试通过用户名查找
        user = await UserService.get_by_username(username_or_email)

        # 如果用户名不存在，尝试通过邮箱查找
        if not user:
            user = await UserService.get_by_email(username_or_email)

        if not user:
            return None

        if not verify_password(password, user.password):
            return None

        # 更新最后登录时间
        user.last_login = datetime.now()
        await user.save()

        return user

    @staticmethod
    async def update_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        修改密码

        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        user = await User.filter(id=user_id).first()
        if not user:
            return False, "用户不存在"

        if not verify_password(old_password, user.password):
            return False, "旧密码错误"

        # 更新密码
        user.password = get_password_hash(new_password)
        await user.save()

        return True, "密码修改成功"

    @staticmethod
    async def get_user_list(
            page: int = 1,
            page_size: int = 10,
            username: Optional[str] = None,
            email: Optional[str] = None,
            is_active: Optional[bool] = None,
            dept_id: Optional[int] = None,
    ) -> Tuple[List[User], int]:
        """
        获取用户列表(分页)

        Args:
            page: 页码
            page_size: 每页数量
            username: 用户名(模糊搜索)
            email: 邮箱(模糊搜索)
            is_active: 是否激活
            dept_id: 部门ID

        Returns:
            Tuple[List[User], int]: (用户列表, 总数)
        """
        query = User.all()

        # 构建查询条件
        if username:
            query = query.filter(username__icontains=username)
        if email:
            query = query.filter(email__icontains=email)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        if dept_id is not None:
            query = query.filter(dept_id=dept_id)

        # 获取总数
        total = await query.count()

        # 分页查询
        offset = (page - 1) * page_size
        users = await query.offset(offset).limit(page_size).order_by('-created_at')

        return users, total

    @staticmethod
    async def check_username_exists(username: str, exclude_id: Optional[int] = None) -> bool:
        """
        检查用户名是否存在

        Args:
            username: 用户名
            exclude_id: 排除的用户ID(用于更新时检查)

        Returns:
            bool: 是否存在
        """
        query = User.filter(username=username)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def check_email_exists(email: str, exclude_id: Optional[int] = None) -> bool:
        """
        检查邮箱是否存在

        Args:
            email: 邮箱
            exclude_id: 排除的用户ID(用于更新时检查)

        Returns:
            bool: 是否存在
        """
        query = User.filter(email=email)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()
