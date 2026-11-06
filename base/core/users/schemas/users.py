"""
用户相关的Pydantic模型
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """用户基础模型"""
    username: str = Field(..., min_length=3, max_length=20, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    alias: Optional[str] = Field(None, max_length=30, description="姓名")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    dept_id: Optional[int] = Field(None, description="部门ID")


class UserCreate(UserBase):
    """创建用户模型"""
    password: str = Field(..., min_length=6, max_length=50, description="密码")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v


class UserUpdate(BaseModel):
    """更新用户模型"""
    alias: Optional[str] = Field(None, max_length=30, description="姓名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    dept_id: Optional[int] = Field(None, description="部门ID")
    is_active: Optional[bool] = Field(None, description="是否激活")


class UserUpdatePassword(BaseModel):
    """修改密码模型"""
    old_password: str = Field(..., min_length=6, description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class UserLogin(BaseModel):
    """用户登录模型（支持用户名或邮箱登录）"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    username: str
    alias: Optional[str] = None
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_superuser: bool
    dept_id: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间(秒)")
    user: UserResponse = Field(..., description="用户信息")


class UserListQuery(BaseModel):
    """用户列表查询参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    username: Optional[str] = Field(None, description="用户名(模糊搜索)")
    email: Optional[str] = Field(None, description="邮箱(模糊搜索)")
    is_active: Optional[bool] = Field(None, description="是否激活")
    dept_id: Optional[int] = Field(None, description="部门ID")


class SendCodeSchema(BaseModel):
    """发送验证码请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    type: str = Field(..., description="类型: register-注册, login-登录, reset_password-重置密码")


class VerifyCodeSchema(BaseModel):
    """验证码验证请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")
    type: str = Field(..., description="类型: register-注册, login-登录")


class EmailLoginSchema(BaseModel):
    """邮箱登录请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="验证码")


class UserListResponse(BaseModel):
    """用户列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: list[UserResponse] = Field(..., description="用户列表")
