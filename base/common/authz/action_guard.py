"""
功能码双轨鉴权依赖（C1 整改，2026-11-17）

背景：
- contentops 业务路由原同时挂 `require_owner`（authz 双主体）与
  `require_permission`（USR/RBAC）。后者内部 `get_current_user_id` 只取 JWT
  `sub`、不校验 `typ`，CUS 的 customer.id 被当 user.id 查 RBAC → 必然 403
  （撞号时错误放行），违反 R-04，CUS 租户无法使用 contentops。
- 本项目铁律：CUS 主体不走 RBAC。故 CUS 的功能码授权改走 resource_grant。

本模块提供 `require_action(code)`：
- USR 分支：复用既有 RBAC 权限码判定（含超管 `*` 通配），行为与旧
  `require_permission` 完全一致，**USR 零回归**；返回 user.id。
- CUS 分支：走 `ResourceGrantService.check_resource_access(owner, 'contentops_action', code)`
  （含 subject 有效性 + 组织 org 继承），未授权 → 404（不暴露功能存在性）；
  返回 customer.id。
- 返回值语义：`int` 操作人 ID，兼容路由里 `creator_id=user_id` 等既有用法。

注意：依赖 CUS 分支不进入 `base.common.permissions` / `get_current_user_id`，
从根上切断 CUS → RBAC 的错误通路。
"""
from typing import Optional

from fastapi import HTTPException, status

from .context import OwnerContext, require_owner
from .constants import OwnerType, ResourceType
from .service import ResourceGrantService
from .filter import OwnedResourceNotFound


def _rbac_dependency(code: str):
    """USR 分支：返回与旧 require_permission 等价的异步依赖（保留 403 语义）。"""
    async def dependency(owner: OwnerContext) -> int:
        # 延迟导入：避免 common.authz 在模块级反向依赖 common.permissions 体系；
        # 且该 import 仅在 USR 请求时触发，CUS 请求永不加载 RBAC 链路。
        from base.common.permissions import get_user_permissions_cached

        user_perms = await get_user_permissions_cached(owner.owner_id)
        if "*" in user_perms:
            return owner.owner_id
        if code not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {code}",
            )
        return owner.owner_id
    return dependency


async def _customer_authorize(owner: OwnerContext, code: str) -> int:
    """CUS 分支：查 resource_grant（含 org 继承）；未授权 404 不暴露功能存在性。"""
    allowed = await ResourceGrantService.check_resource_access(
        owner,
        resource_type=ResourceType.CONTENTOPS_ACTION.value,
        resource_id=code,
    )
    if not allowed:
        # 404 而非 403：不向未授权租户暴露"该功能存在"这一信息（对齐 F8 归属 404 语义）。
        raise OwnedResourceNotFound()
    return owner.owner_id


def require_action(code: str):
    """
    功能码双轨鉴权依赖工厂。

    用法（替换 require_permission）：
        @router.post("/check")
        async def check(
            owner: OwnerContext = Depends(require_owner),
            user_id: int = require_action("contentops:compliance:check"),
        ):
            ...

    返回 FastAPI Depends，注入 int 操作人 ID（USR=user.id / CUS=customer.id）。
    """
    from fastapi import Depends

    rbac_dep = _rbac_dependency(code)

    async def dependency(owner: OwnerContext = Depends(require_owner)) -> int:
        if owner.is_admin_user:
            return await rbac_dep(owner)
        if owner.is_customer:
            return await _customer_authorize(owner, code)
        # 理论不可达：require_owner 已放行 cus/usr 之外的 typ 会 401；此处纵深防御。
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Depends(dependency)
