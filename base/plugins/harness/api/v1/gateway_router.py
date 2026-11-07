"""Harness 网关租约签发/续期/吊销（控制面，客户端凭据鉴权）"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from base.common.response import success_response
from base.plugins.harness.services.client_service import require_harness_client
from base.plugins.harness.services.gateway_lease_service import GatewayLeaseService

gateway_router = APIRouter(prefix="/gateway/leases", tags=["Harness-网关租约"])


class LeaseIssueSchema(BaseModel):
    session_no: Optional[str] = Field(None, description="绑定会话（推荐；与 run 二选一或同时）")
    run_no: Optional[str] = Field(None, description="绑定运行")
    ttl_seconds: Optional[int] = Field(None, ge=30, le=3600, description="租约有效秒数")
    rpm_limit: Optional[int] = Field(None, ge=1, le=10000, description="每分钟请求上限")
    provider: Optional[str] = Field(None, description="provider（缺省取 run/凭据默认）")
    model: Optional[str] = Field(None, description="model（缺省取 run/凭据默认）")
    budget_tokens: Optional[int] = Field(None, ge=0, description="租约 token 预算（0/缺省=按网关配置）")


class LeaseRenewSchema(BaseModel):
    ttl_seconds: Optional[int] = Field(None, ge=30, le=3600)


@gateway_router.post("", summary="签发网关虚拟 key 租约")
async def issue_lease(payload: LeaseIssueSchema, client=Depends(require_harness_client)):
    data = await GatewayLeaseService.issue(
        client,
        session_no=payload.session_no,
        run_no=payload.run_no,
        ttl_seconds=payload.ttl_seconds,
        rpm_limit=payload.rpm_limit,
        provider=payload.provider,
        model=payload.model,
        budget_tokens=payload.budget_tokens,
    )
    return success_response(data=data, msg="租约已签发（虚拟 key 仅此一次返回）")


@gateway_router.post("/{lease_id}/renew", summary="续期网关租约")
async def renew_lease(
    lease_id: str, payload: LeaseRenewSchema, client=Depends(require_harness_client),
):
    data = await GatewayLeaseService.renew(lease_id, client, payload.ttl_seconds)
    return success_response(data=data, msg="租约已续期")


@gateway_router.delete("/{lease_id}", summary="吊销网关租约")
async def revoke_lease(lease_id: str, client=Depends(require_harness_client)):
    data = await GatewayLeaseService.revoke(lease_id, client.client_id)
    return success_response(data=data, msg="租约已吊销")


@gateway_router.get("", summary="查询当前客户端的有效租约")
async def list_leases(
    active_only: bool = Query(True),
    client=Depends(require_harness_client),
):
    data = await GatewayLeaseService.list_leases(client.client_id, active_only=active_only)
    return success_response(data={"items": data})
