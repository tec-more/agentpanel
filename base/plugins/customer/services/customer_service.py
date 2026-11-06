"""
客户服务层
"""
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

# 导入依赖项
from base.plugins.customer.models.customer import Customer
from base.plugins.customer.schemas.customer_schema import CustomerCreate, CustomerUpdate
from base.common.security import get_password_hash, verify_password
class CustomerService:
    model = "customer"
    """客户服务类"""

    @staticmethod
    async def get_by_id(customer_id: int) -> Optional[Customer]:
        """
        根据ID获取客户

        Args:
            customer_id: 客户ID

        Returns:
            Optional[Customer]: 客户对象,不存在返回None
        """
        return await Customer.filter(id=customer_id).first()

    @staticmethod
    async def get_by_username(username: str) -> Optional[Customer]:
        """
        根据用户名获取客户

        Args:
            username: 用户名

        Returns:
            Optional[Customer]: 客户对象,不存在返回None
        """
        return await Customer.filter(username=username).first()

    @staticmethod
    async def get_by_email(email: str) -> Optional[Customer]:
        """
        根据邮箱获取客户

        Args:
            email: 邮箱

        Returns:
            Optional[Customer]: 客户对象,不存在返回None
        """
        return await Customer.filter(email=email).first()

    @staticmethod
    async def get_by_phone(phone: str) -> Optional[Customer]:
        """
        根据手机号获取客户

        Args:
            phone: 手机号

        Returns:
            Optional[Customer]: 客户对象,不存在返回None
        """
        return await Customer.filter(phone=phone).first()

    @staticmethod
    async def register_customer(customer_data: CustomerCreate) -> Customer:
        """
        注册新客户

        Args:
            customer_data: 客户注册数据

        Returns:
            Customer: 创建的客户对象

        Raises:
            ValueError: 用户名/邮箱/手机号已存在
        """
        # 检查用户名是否已存在
        if await CustomerService.check_username_exists(customer_data.username):
            raise ValueError("用户名已存在")

        # 检查邮箱是否已存在
        if await CustomerService.check_email_exists(customer_data.email):
            raise ValueError("邮箱已存在")

        # 检查手机号是否已存在（如果提供）
        if customer_data.phone and await CustomerService.check_phone_exists(customer_data.phone):
            raise ValueError("手机号已存在")

        # 密码加密
        hashed_password = get_password_hash(customer_data.password)

        # 创建用户
        customer = await Customer.create(
            username=customer_data.username,
            email=customer_data.email,
            phone=customer_data.phone,
            password=hashed_password,
            nickname=customer_data.nickname,
            gender=customer_data.gender,
            birthday=customer_data.birthday,
            address=customer_data.address,
        )

        return customer

    @staticmethod
    async def login_customer(email: str, password: str) -> Dict[str, Any]:
        """
        客户登录

        Args:
            email: 邮箱
            password: 密码

        Returns:
            Dict[str, Any]: 登录结果，包含客户信息和token

        Raises:
            ValueError: 邮箱或密码错误，或客户未激活
        """
        # 根据邮箱获取用户
        customer = await CustomerService.get_by_email(email)
        if not customer:
            raise ValueError("邮箱或密码错误")

        # 验证密码
        if not verify_password(password, customer.password):
            raise ValueError("邮箱或密码错误")

        # 检查用户是否已激活
        if not customer.is_active:
            raise ValueError("用户已被禁用")

        # 更新登录信息
        customer.last_login = datetime.now()
        customer.login_count += 1
        await customer.save()

        # 将Customer对象转换为字典
        if hasattr(customer, 'to_dict'):
            customer_dict = await customer.to_dict()
        elif hasattr(customer, 'dict'):
            customer_dict = customer.dict()
        else:
            customer_dict = dict(customer)

        # 生成token（这里只返回模拟数据，实际项目中需要实现JWT生成）
        token_data = {
            "access_token": "mock_jwt_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "user": customer_dict
        }

        return token_data

    @staticmethod
    async def get_customer_info(customer_id: int) -> Optional[Customer]:
        """
        获取客户信息

        Args:
            customer_id: 客户ID

        Returns:
            Optional[Customer]: 客户对象,不存在返回None
        """
        return await CustomerService.get_by_id(customer_id)

    @staticmethod
    async def update_customer_info(customer_id: int, customer_data: CustomerUpdate) -> Optional[Customer]:
        """
        更新客户信息

        Args:
            customer_id: 客户ID
            customer_data: 更新数据

        Returns:
            Optional[Customer]: 更新后的客户对象

        Raises:
            ValueError: 用户名/邮箱/手机号已被其他客户使用
        """
        customer = await Customer.filter(id=customer_id).first()
        if not customer:
            return None

        # 检查用户名是否被其他用户使用
        if customer_data.username and customer_data.username != customer.username:
            if await CustomerService.check_username_exists(customer_data.username, exclude_id=customer_id):
                raise ValueError("用户名已被使用")

        # 检查邮箱是否被其他用户使用
        if customer_data.email and customer_data.email != customer.email:
            if await CustomerService.check_email_exists(customer_data.email, exclude_id=customer_id):
                raise ValueError("邮箱已被使用")

        # 检查手机号是否被其他用户使用
        if customer_data.phone and customer_data.phone != customer.phone:
            if await CustomerService.check_phone_exists(customer_data.phone, exclude_id=customer_id):
                raise ValueError("手机号已被使用")

        # 密码加密（如果提供）
        if customer_data.password:
            customer_data.password = get_password_hash(customer_data.password)

        # 只更新提供的字段
        update_data = customer_data.model_dump(exclude_unset=True)
        await customer.update_from_dict(update_data).save()

        return customer

    @staticmethod
    async def delete_customer(customer_id: int) -> bool:
        """
        删除客户

        Args:
            customer_id: 客户ID

        Returns:
            bool: 是否删除成功
        """
        deleted_count = await Customer.filter(id=customer_id).delete()
        return deleted_count > 0

    @staticmethod
    async def toggle_customer_status(customer_id: int) -> Optional[Customer]:
        """
        切换客户激活状态

        Args:
            customer_id: 客户ID

        Returns:
            Optional[Customer]: 更新后的客户对象
        """
        customer = await Customer.filter(id=customer_id).first()
        if not customer:
            return None

        # 切换状态
        customer.is_active = not customer.is_active
        await customer.save()

        return customer

    @staticmethod
    async def get_customer_list(
            page: int = 1,
            page_size: int = 10,
            username: Optional[str] = None,
            email: Optional[str] = None,
            phone: Optional[str] = None,
            is_active: Optional[bool] = None,
            is_verified: Optional[bool] = None,
    ) -> Tuple[List[Customer], int]:
        """
        获取客户列表(分页)

        Args:
            page: 页码
            page_size: 每页数量
            username: 用户名(模糊搜索)
            email: 邮箱(模糊搜索)
            phone: 手机号(模糊搜索)
            is_active: 是否激活
            is_verified: 是否已验证

        Returns:
            Tuple[List[Customer], int]: (客户列表, 总数)
        """
        query = Customer.all()

        # 构建查询条件
        if username:
            query = query.filter(username__icontains=username)
        if email:
            query = query.filter(email__icontains=email)
        if phone:
            query = query.filter(phone__icontains=phone)
        if is_active is not None:
            query = query.filter(is_active=is_active)
        if is_verified is not None:
            query = query.filter(is_verified=is_verified)

        # 获取总数
        total = await query.count()

        # 分页查询
        offset = (page - 1) * page_size
        customers = await query.offset(offset).limit(page_size).order_by('-created_at')

        return customers, total

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
        query = Customer.filter(username=username)
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
        query = Customer.filter(email=email)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def check_phone_exists(phone: str, exclude_id: Optional[int] = None) -> bool:
        """
        检查手机号是否存在

        Args:
            phone: 手机号
            exclude_id: 排除的用户ID(用于更新时检查)

        Returns:
            bool: 是否存在
        """
        query = Customer.filter(phone=phone)
        if exclude_id:
            query = query.exclude(id=exclude_id)
        return await query.exists()

    @staticmethod
    async def update_customer_points(customer_id: int, points: int) -> Optional[Customer]:
        """
        更新客户积分

        Args:
            customer_id: 客户ID
            points: 积分值

        Returns:
            Optional[Customer]: 更新后的客户对象
        """
        customer = await Customer.filter(id=customer_id).first()
        if not customer:
            return None

        # 更新积分
        customer.points = points
        await customer.save()

        return customer

    @staticmethod
    async def update_customer_membership(customer_id: int, membership_expire: Optional[datetime] = None) -> Optional[Customer]:
        """
        更新客户会员到期日期

        Args:
            customer_id: 客户ID
            membership_expire: 会员到期日期

        Returns:
            Optional[Customer]: 更新后的客户对象
        """
        customer = await Customer.filter(id=customer_id).first()
        if not customer:
            return None

        # 更新会员到期日期
        if membership_expire:
            customer.membership_expire = membership_expire
            await customer.save()

        return customer