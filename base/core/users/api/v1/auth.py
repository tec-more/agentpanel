"""
用户认证API
"""
from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends, Request

from base.core.users.schemas.users import (
    UserLogin,
    UserCreate,
    UserUpdate,
    TokenResponse,
    UserResponse,
    UserUpdatePassword,
    SendCodeSchema,
    VerifyCodeSchema,
    EmailLoginSchema,
)
from base.core.users.services.user_service import UserService
from base.core.users.services.email_service import EmailService
from base.common.security import (
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user_id,
)
from base.common.response import SuccessResponse, ErrorResponse
from base.common.setting import settings


def is_login_log_enabled() -> bool:
    return getattr(settings, 'AUDIT_ENABLED', True) and getattr(settings, 'AUDIT_LOG_LOGIN', True)


def get_event_bus():
    """延迟导入事件总线，确保处理器已注册"""
    from base.common.events.event_bus import event_bus
    return event_bus


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

router = APIRouter(prefix="/v1/auth", tags=["认证管理"])


@router.post("/register", summary="管理员注册用户（仅限内部调用）", response_model=UserResponse)
async def register(user_data: UserCreate):
    """
    管理员注册新用户
    注意：此接口仅用于后台管理员创建，普通用户注册请使用客户接口 /api/v1/customer/auth/register

    Args:
        user_data: 用户注册数据

    Returns:
        创建的用户信息
    """
    # 检查用户名是否存在
    if await UserService.check_username_exists(user_data.username):
        return ErrorResponse(msg="用户名已存在", status_code=status.HTTP_400_BAD_REQUEST)

    # 检查邮箱是否存在
    if await UserService.check_email_exists(user_data.email):
        return ErrorResponse(msg="邮箱已被注册", status_code=status.HTTP_400_BAD_REQUEST)

    # 创建用户（管理员）
    user = await UserService.create_user(user_data)

    # 转换为响应模型
    user_dict = await user.to_dict()
    return SuccessResponse(data=user_dict, msg="管理员创建成功")


@router.post("/login", summary="用户登录")
async def login(login_data: UserLogin, request: Request):
    """
    用户登录

    Args:
        login_data: 登录数据

    Returns:
        Token和用户信息
    """
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    async def log_login(username: str, user_id: int = None, success: bool = True, fail_reason: str = None):
        if not is_login_log_enabled():
            return
        event_bus = get_event_bus()
        handlers = event_bus.get_handlers('user.login') if hasattr(event_bus, 'get_handlers') else event_bus._handlers.get('user.login', [])
        print(f"[登录] 获取事件总线实例ID: {id(event_bus)}, user.login 订阅者: {len(handlers)}")
        await event_bus.publish(
            "user.login",
            user_id=user_id,
            username=username,
            login_type="login",
            login_method="password",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            fail_reason=fail_reason
        )

    # 验证用户
    user = await UserService.authenticate(login_data.username, login_data.password)
    if not user:
        await log_login(login_data.username, success=False, fail_reason="用户名或密码错误")
        return ErrorResponse(
            msg="用户名或密码错误",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # 检查用户是否激活
    if not user.is_active:
        await log_login(user.username, user.id, success=False, fail_reason="账号已被禁用")
        return ErrorResponse(
            msg="账号已被禁用,请联系管理员",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # 创建访问令牌 - sub 必须是字符串
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "typ": "usr", "username": user.username},
        expires_delta=access_token_expires
    )

    # 记录登录成功日志
    await log_login(user.username, user.id, success=True)

    # 获取用户信息
    user_dict = await user.to_dict()

    # 返回token和用户信息
    token_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user_dict
    }

    return SuccessResponse(data=token_data, msg="登录成功")


@router.get("/me", summary="获取当前用户信息")
async def get_current_user(user_id: int = Depends(get_current_user_id)):
    """
    获取当前登录用户的信息

    Args:
        user_id: 从token中解析的用户ID

    Returns:
        用户信息
    """
    user = await UserService.get_by_id(user_id)
    if not user:
        return ErrorResponse(
            msg="用户不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    user_dict = await user.to_dict()
    return SuccessResponse(data=user_dict)


@router.post("/change-password", summary="修改密码")
async def change_password(
        password_data: UserUpdatePassword,
        user_id: int = Depends(get_current_user_id)
):
    """
    修改当前用户密码

    Args:
        password_data: 密码修改数据
        user_id: 从token中解析的用户ID

    Returns:
        修改结果
    """
    success, message = await UserService.update_password(
        user_id,
        password_data.old_password,
        password_data.new_password
    )

    if success:
        return SuccessResponse(msg=message)
    else:
        return ErrorResponse(msg=message, status_code=status.HTTP_400_BAD_REQUEST)


@router.post("/send-code", summary="发送管理员验证码（已弃用）")
async def send_code(code_data: SendCodeSchema):
    """
    发送验证码到管理员邮箱
    注意：此接口已弃用，管理员请使用用户名密码登录。普通用户请使用 /api/v1/customer/auth/send-code

    Args:
        code_data: 邮箱和验证码类型

    Returns:
        发送结果
    """
    return ErrorResponse(
        msg="此接口已弃用。普通用户请使用 /api/v1/customer/auth/send-code，管理员请使用用户名密码登录",
        status_code=status.HTTP_410_GONE
    )


@router.post("/email-login", summary="管理员邮箱验证码登录（已弃用）")
async def email_login(login_data: EmailLoginSchema):
    """
    使用邮箱和验证码登录（管理员）
    注意：此接口已弃用。普通用户请使用 /api/v1/customer/auth/login-code，管理员请使用用户名密码登录

    Args:
        login_data: 邮箱和验证码

    Returns:
        Token和用户信息
    """
    return ErrorResponse(
        msg="此接口已弃用。普通用户请使用 /api/v1/customer/auth/login-code，管理员请使用用户名密码登录",
        status_code=status.HTTP_410_GONE
    )


@router.put("/update-profile", summary="更新当前用户信息")
async def update_profile(
        profile_data: UserUpdate,
        user_id: int = Depends(get_current_user_id)
):
    """
    更新当前登录用户的个人信息

    Args:
        profile_data: 用户更新数据
        user_id: 从token中解析的用户ID

    Returns:
        更新后的用户信息
    """
    # 检查邮箱是否被其他用户使用
    if profile_data.email:
        if await UserService.check_email_exists(profile_data.email, exclude_id=user_id):
            return ErrorResponse(
                msg="邮箱已被其他用户使用",
                status_code=status.HTTP_400_BAD_REQUEST
            )

    # 更新用户
    user = await UserService.update_user(user_id, profile_data)
    if not user:
        return ErrorResponse(
            msg="用户不存在",
            status_code=status.HTTP_404_NOT_FOUND
        )

    user_dict = await user.to_dict()
    return SuccessResponse(data=user_dict, msg="更新成功")


@router.post("/logout", summary="用户登出")
async def logout(request: Request, user_id: int = Depends(get_current_user_id)):
    """
    用户登出(客户端需要删除本地token)

    Args:
        user_id: 从token中解析的用户ID

    Returns:
        登出成功消息
    """
    if is_login_log_enabled():
        user = await UserService.get_by_id(user_id)
        if user:
            ip_address = get_client_ip(request)
            user_agent = request.headers.get("user-agent")
            
            event_bus = get_event_bus()
            await event_bus.publish(
                "user.logout",
                user_id=user.id,
                username=user.username,
                login_type="logout",
                login_method="password",
                ip_address=ip_address,
                user_agent=user_agent,
                success=True
            )
    
    return SuccessResponse(msg="登出成功")
