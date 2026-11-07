"""Harness 审批联动（三档策略，默认后端侧挡，fail-closed）"""
from fastapi import APIRouter, Depends, Query

from base.common.response import success_response
from base.plugins.harness.schemas.harness import ApprovalDecide, ApprovalRequest
from base.plugins.harness.services.approval_service import HarnessApprovalService
from base.plugins.harness.services.client_service import require_harness_client

approval_router = APIRouter(prefix="/approvals", tags=["Harness-审批"])


@approval_router.post("/request", summary="申请审批（三档策略判定）")
async def request_approval(
    payload: ApprovalRequest,
    client=Depends(require_harness_client),
):
    data = await HarnessApprovalService.request(client.client_id, payload)
    return success_response(data=data, msg="审批判定完成")


@approval_router.get("/pending", summary="待审批列表（触发超时拒绝结算）")
async def list_pending(
    approver: str = Query(None, description="审批人用户 ID/用户名；为空返回当前客户端全部待审批"),
    client=Depends(require_harness_client),
):
    data = await HarnessApprovalService.pending(client.client_id, approver)
    return success_response(data={"total": len(data), "items": data}, msg="待审批列表")


@approval_router.post("/{approval_no}/decision", summary="回写审批决策")
async def decide_approval(
    approval_no: str,
    payload: ApprovalDecide,
    client=Depends(require_harness_client),
):
    data = await HarnessApprovalService.decide(client.client_id, approval_no, payload)
    return success_response(data=data, msg="审批决策已记录")

