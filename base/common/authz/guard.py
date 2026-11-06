"""
L3 服务层复核钩子

溯源：docs/arch/05 §2.1 L3——M8 复核：写操作与敏感读二次校验 owner（最后防线，必测）。

定位：L2 声明式过滤之后的纵深防御，供 T5/T6 服务层在写操作/敏感读前调用；
本任务只交付能力，不接入具体业务服务。

用法：
    # 服务层写操作前复核（不匹配抛 404 并记越权审计）
    await assert_owner_access(workflow, for_write=True)

    # 引擎/内部调用非抛出式复核（R-02：引擎只消费 M8 判定结果）
    if not await recheck_owner(workflow, owner):
        ...
"""
from typing import Optional

from fastapi import HTTPException, status
from tortoise.models import Model

from .audit import record_violation
from .context import OwnerContext, get_current_owner
from .filter import OwnedResourceNotFound, is_accessible


async def assert_owner_access(
    obj: Model,
    owner: Optional[OwnerContext] = None,
    *,
    for_write: bool = True,
) -> None:
    """
    服务层二次归属校验（写操作/敏感读用），不匹配抛 404 + 越权审计

    Args:
        obj: 归属资源实例（须具备 owner_type/owner_id）
        owner: 主体上下文，默认取当前请求上下文
        for_write: 写操作语义（默认 True：严格归属，不接受公开只读）

    Raises:
        HTTPException 401: 无认证上下文
        OwnedResourceNotFound 404: 归属不匹配（已记录审计）
    """
    if owner is None:
        owner = get_current_owner()
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not is_accessible(obj, owner, include_public=False, for_write=for_write):
        await record_violation(
            owner.identity,
            path=owner.request_path or "-",
            method=owner.request_method or "-",
            resource_hint=f"{obj._meta.db_table}:{obj.pk}(L3)",
        )
        raise OwnedResourceNotFound()


async def recheck_owner(
    obj: Model,
    owner: Optional[OwnerContext] = None,
    *,
    for_write: bool = True,
) -> bool:
    """
    非抛出式归属复核（引擎/内部服务消费判定结果，R-02）

    Returns:
        True=归属校验通过；False=不匹配（调用方决定处置，判定留痕由调用方触发）
    """
    if owner is None:
        owner = get_current_owner()
    if owner is None:
        return False
    return is_accessible(obj, owner, include_public=False, for_write=for_write)
