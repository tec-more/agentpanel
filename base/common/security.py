"""
安全相关工具函数
"""
from datetime import datetime, timedelta
from typing import Any, Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT配置
SECRET_KEY = "your-secret-key-change-in-production-09876543210987654321"  # 生产环境需要改成环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# HTTP Bearer Token
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 加密后的密码

    Returns:
        bool: 密码是否匹配
    """
    truncated_password = plain_password[:72]
    return pwd_context.verify(truncated_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    加密密码

    Args:
        password: 明文密码

    Returns:
        str: 加密后的密码
    """
    truncated_password = password[:72]
    return pwd_context.hash(truncated_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        str: JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    解码JWT令牌

    Args:
        token: JWT token

    Returns:
        Optional[dict]: 解码后的数据,如果失败返回None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """
    从JWT令牌中获取当前用户ID

    Args:
        credentials: HTTP Authorization 凭证

    Returns:
        int: 用户ID

    Raises:
        HTTPException: 如果令牌无效或已过期
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    从JWT令牌中获取当前用户对象

    Args:
        credentials: HTTP Authorization 凭证

    Returns:
        User: 用户对象

    Raises:
        HTTPException: 如果令牌无效或用户不存在
    """
    from base.core.users.models.users import User

    user_id = await get_current_user_id(credentials)
    user = await User.filter(id=user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_actor(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    token = credentials.credentials
    print(f"[AUTH DEBUG] Token received (first 50 chars): {token[:50]}...")
    
    payload = decode_access_token(token)
    print(f"[AUTH DEBUG] Decoded payload: {payload}")
    
    if not payload:
        print("[AUTH DEBUG] Token decode failed! Check SECRET_KEY or token format.")
        raise HTTPException(status_code=401)

    # 现在这两个都有值了！
    user_id = payload.get("sub")
    user_type = payload.get("typ")
    print(f"[AUTH DEBUG] user_id: {user_id}, user_type: {user_type}")

    if not user_id or not user_type:
        print(f"[AUTH DEBUG] Missing user_id or user_type! user_id={user_id}, user_type={user_type}")
        raise HTTPException(status_code=401, detail="请重新登录")

    return {
        "type": user_type,
        "id": user_id
    }
async def get_current_user_id_ws(token: str = None) -> Optional[int]:
    """
    从JWT令牌中获取当前用户ID（WebSocket专用）
    
    WebSocket不支持HTTP Authorization header，所以通过query parameter传递token
    
    Args:
        token: JWT令牌字符串（通过query parameter传递）
    
    Returns:
        Optional[int]: 用户ID，如果token无效返回None
    """
    if not token:
        return None
    
    payload = decode_access_token(token)
    
    if payload is None:
        return None
    
    user_id_str = payload.get("sub")
    if user_id_str is None:
        return None
    
    try:
        user_id = int(user_id_str)
        return user_id
    except (ValueError, TypeError):
        return None
