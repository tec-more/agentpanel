"""
客户相关的Pydantic模型
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from decimal import Decimal


class CustomerBase(BaseModel):
    """客户基础模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    gender: Optional[int] = Field(0, ge=0, le=2, description="性别: 0-未知, 1-男, 2-女")
    birthday: Optional[datetime] = Field(None, description="生日")
    address: Optional[str] = Field(None, max_length=255, description="地址")


class CustomerCreate(CustomerBase):
    """创建客户模型"""
    password: str = Field(..., min_length=6, max_length=50, description="密码")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v


class CustomerUpdate(BaseModel):
    """更新客户模型"""
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    nickname: Optional[str] = Field(None, max_length=50, description="昵称")
    avatar: Optional[str] = Field(None, max_length=255, description="头像URL")
    gender: Optional[int] = Field(None, ge=0, le=2, description="性别: 0-未知, 1-男, 2-女")
    birthday: Optional[datetime] = Field(None, description="生日")
    address: Optional[str] = Field(None, max_length=255, description="地址")


class CustomerUpdatePassword(BaseModel):
    """修改密码模型"""
    old_password: str = Field(..., min_length=6, description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError('新密码长度至少6位')
        return v


class CustomerLogin(BaseModel):
    """用户登录模型"""
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., description="密码")


class CustomerResponse(BaseModel):
    """客户响应模型"""
    id: int
    username: str
    email: str
    phone: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    gender: int
    birthday: Optional[datetime] = None
    address: Optional[str] = None
    is_active: bool
    is_verified: bool
    points: int
    balance: Decimal
    last_login: Optional[datetime] = None
    login_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerTokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")
    user: CustomerResponse = Field(..., description="用户信息")


class CustomerListQuery(BaseModel):
    """用户列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    username: Optional[str] = Field(None, description="用户名(模糊搜索)")
    email: Optional[str] = Field(None, description="邮箱(模糊搜索)")
    phone: Optional[str] = Field(None, description="手机号(模糊搜索)")
    nickname: Optional[str] = Field(None, description="昵称(模糊搜索)")
    is_active: Optional[bool] = Field(None, description="是否激活")
    is_verified: Optional[bool] = Field(None, description="是否已验证")


class CustomerListResponse(BaseModel):
    """用户列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[CustomerResponse] = Field(..., description="用户列表")