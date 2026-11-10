"""客户账号直签网关租约（控制面，customer JWT 鉴权）

设计约束：
- 网关数据面只接受 ``dgw.<lease_id>.<secret>`` 虚拟 key，业务接口只接受 JWT，
  两者双向隔离；桌面端不能把登录态 JWT 直接当网关 key 使用。
- 本端点把「已通过邮箱验证码注册 / 登录的 customer」映射成一张绑定
  ``owner_type="cus"`` / ``owner_id=customer.id`` 的租约，桌面端拿到的仍是虚拟 key。
- 租约的 client_id 固定为 ``cus:<customer_id>``，续期与吊销都只能操作
  该账号自己签发的租约，不影响 Harness 客户端凭据签发的租约。
"""
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from base.common.response import success_response
from base.common.security import get_current_actor
from base.plugins.harness.services.gateway_lease_service import GatewayLeaseService

lease_router = APIRouter(prefix="/leases", tags=["客户认证-网关租约"])


class CustomerLeaseIssueSchema(BaseModel):
    """账号直签租约的可选参数；主体一律由鉴权层决定，不接受调用方指定。"""

    ttl_seconds: Optional[int] = Field(None, ge=30, le=3600, description="租约有效秒数")
    rpm_limit: Optional[int] = Field(None, ge=1, le=10000, description="每分钟请求上限")
    provider: Optional[str] = Field(None, max_length=50, description="provider")
    model: Optional[str] = Field(None, max_length=100, description="model")
    budget_tokens: Optional[int] = Field(None, ge=0, description="租约 token 预算")


class CustomerLeaseRenewSchema(BaseModel):
    ttl_seconds: Optional[int] = Field(None, ge=30, le=3600)


async def _customer_client(actor: dict) -> SimpleNamespace:
    """校验 JWT 主体确为有效客户，并构造与租约服务兼容的最小客户端标识。"""
    if actor.get("type") != "cus":
        raise HTTPException(status_code=403, detail="仅客户账号可签发账号租约")
    try:
        customer_id = int(actor["id"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="无效的认证凭据")

    from base.plugins.customer.models.customer import Customer

    customer = await Customer.get_or_none(id=customer_id)
    if customer is None or not customer.is_active:
        raise HTTPException(status_code=403, detail="客户账号不存在或已停用")
    # 与 GatewayLeaseService.renew 的 client_id / status 约定保持一致。
    return SimpleNamespace(client_id=f"cus:{customer_id}", status="active")


@lease_router.post("", summary="用客户登录态签发网关虚拟 key 租约")
async def issue_customer_lease(
    payload: CustomerLeaseIssueSchema,
    actor: dict = Depends(get_current_actor),
):
    client = await _customer_client(actor)
    data = await GatewayLeaseService.issue(
        client,
        ttl_seconds=payload.ttl_seconds,
        rpm_limit=payload.rpm_limit,
        provider=payload.provider,
        model=payload.model,
        budget_tokens=payload.budget_tokens,
        owner_override=("cus", int(actor["id"])),
    )
    return success_response(data=data, msg="租约已签发（虚拟 key 仅此一次返回）")


@lease_router.post("/{lease_id}/renew", summary="续期客户账号租约")
async def renew_customer_lease(
    lease_id: str,
    payload: CustomerLeaseRenewSchema,
    actor: dict = Depends(get_current_actor),
):
    client = await _customer_client(actor)
    data = await GatewayLeaseService.renew(lease_id, client, payload.ttl_seconds)
    return success_response(data=data, msg="租约已续期")


@lease_router.delete("/{lease_id}", summary="吊销客户账号租约")
async def revoke_customer_lease(
    lease_id: str,
    actor: dict = Depends(get_current_actor),
):
    client = await _customer_client(actor)
    data = await GatewayLeaseService.revoke(lease_id, client.client_id)
    return success_response(data=data, msg="租约已吊销")


@lease_router.get("", summary="查询当前客户账号的有效租约")
async def list_customer_leases(
    active_only: bool = Query(True),
    actor: dict = Depends(get_current_actor),
):
    client = await _customer_client(actor)
    data = await GatewayLeaseService.list_leases(client.client_id, active_only)
    return success_response(data={"items": data})
