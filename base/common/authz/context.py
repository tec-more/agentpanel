"""
L1 接入层：JWT 双主体上下文（owner context）

溯源：
- docs/arch/05 §2.1 L1：JWT typ/sub 同源校验（RK-13 已修），统一注入 owner 上下文
- R-04：信任 typ/sub 同源，禁止兼容旧 token 语义、禁止跨表借用 ID

说明：
- 复用 base.common.security.decode_access_token 做签名校验（签发逻辑不动）
- typ=cus → 客户主体（customer_id）；typ=usr → 后台用户主体（user_id，叠加 RBAC data_scope）
- 上下文经 ContextVar 在请求作用域内传递，L2 过滤/L3 复核/审计均从此读取
"""
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from base.common.security import decode_access_token
from .constants import OwnerType, DataScope

# 请求作用域 owner 上下文（middleware 写入，业务/服务层读取）
current_owner: ContextVar[Optional["OwnerContext"]] = ContextVar("current_owner", default=None)

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class OwnerContext:
    """
    双主体归属上下文（不可变，请求级）

    - owner_type: cus/usr（来自 JWT typ 声明，R-04 信任同源）
    - owner_id: 主体 ID（来自 JWT sub）
    - data_scope: 仅 usr 有效（RBAC 数据权限范围），cus 恒为 self
    - org_ids: usr 为数据范围覆盖的部门 ID 集合；cus 为客户组织 ID 集合（T3 扩展，P0 为空）
    - visible_user_ids: usr 数据范围解析出的可见属主用户 ID 集合（L1 一次性解析；
      None 表示不限制（all）或按 owner_id 过滤（self）；dept/dept_tree/custom 为部门成员集合）
    - is_superuser: usr 超管标记（data_scope=all 的快捷判定）
    - request_path/request_method: 请求定位信息（中间件注入，越权审计用）
    """
    owner_type: str
    owner_id: int
    data_scope: str = DataScope.SELF.value
    org_ids: List[int] = field(default_factory=list)
    visible_user_ids: Optional[List[int]] = None
    is_superuser: bool = False
    request_path: str = ""
    request_method: str = ""

    @property
    def is_customer(self) -> bool:
        return self.owner_type == OwnerType.CUS.value

    @property
    def is_admin_user(self) -> bool:
        return self.owner_type == OwnerType.USR.value

    @property
    def identity(self) -> str:
        """限流/审计用的主体标识"""
        return f"{self.owner_type}:{self.owner_id}"


def set_owner_context(owner: Optional[OwnerContext]) -> None:
    current_owner.set(owner)


def clear_owner_context() -> None:
    current_owner.set(None)


def get_current_owner() -> Optional[OwnerContext]:
    """读取当前请求 owner 上下文（未认证请求返回 None）"""
    return current_owner.get()


def parse_owner_payload(payload: dict) -> Optional[OwnerContext]:
    """
    从 JWT payload 构建基础 owner 上下文（不含 data_scope，usr 的 data_scope 由中间件异步叠加）

    R-04：仅信任 typ/sub 同源语义；typ 非 cus/usr 或 sub 缺失/非数值一律视为非法。
    """
    if not payload:
        return None
    typ = payload.get("typ")
    sub = payload.get("sub")
    if typ not in (OwnerType.CUS.value, OwnerType.USR.value) or sub is None:
        return None
    try:
        owner_id = int(sub)
    except (ValueError, TypeError):
        return None
    return OwnerContext(owner_type=typ, owner_id=owner_id)


def parse_owner_token(token: str) -> Optional[OwnerContext]:
    """解析 Bearer token 为基础 owner 上下文；签名非法/语义非法返回 None"""
    return parse_owner_payload(decode_access_token(token))


async def resolve_full_owner(owner: OwnerContext) -> OwnerContext:
    """
    叠加数据权限范围，生成完整上下文（L1 一次性解析，L2 过滤即可保持纯同步）

    - usr：查询现有 RBAC（DataPermissionService）叠加 data_scope、部门集合与可见属主用户集合
    - cus：恒为 self（客户组织维度由 T3/M11 扩展）
    """
    if owner.owner_type != OwnerType.USR.value:
        return owner
    from .scope import resolve_scope, resolve_scope_user_ids  # 延迟导入避免环
    scope = await resolve_scope(owner)
    scoped = OwnerContext(
        owner_type=owner.owner_type,
        owner_id=owner.owner_id,
        data_scope=scope["data_scope"],
        org_ids=scope["org_ids"],
        is_superuser=scope["data_scope"] == DataScope.ALL.value and scope.get("is_superuser", False),
        request_path=owner.request_path,
        request_method=owner.request_method,
    )
    visible_user_ids = await resolve_scope_user_ids(scoped)
    return replace(scoped, visible_user_ids=visible_user_ids)


async def require_owner(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> OwnerContext:
    """
    FastAPI 依赖：要求已认证的双主体上下文（L1）

    用法（T5/T6 业务接口接入）：
        @router.get("/workflows")
        async def list_mine(owner: OwnerContext = Depends(require_owner)):
            query = owned_queryset(Workflow)
            ...

    未携带/非法 token → 401；合法 token → 完整 owner 上下文（usr 已叠加 data_scope）。
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    owner = parse_owner_token(credentials.credentials)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await resolve_full_owner(owner)
