"""Harness 用量看板与预占对账（管理员）"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from services.gateway.gateway.budget import GatewayBudgetService
from base.common.permissions import require_superuser
from base.common.response import success_response, fail_response
from base.plugins.harness.services.dashboard_service import HarnessDashboardService
from base.plugins.harness.services.gateway_lease_service import GatewayLeaseService
from base.plugins.harness.services.reconcile_service import HarnessReconcileService

dashboard_router = APIRouter(prefix="/dashboard", tags=["Harness-看板"])


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dashboard_router.get("/usage", summary="全局用量看板（按来源/类型/模型/租户/客户端分组）")
async def usage_overview(
    source: Optional[str] = Query(None, description="provider/gateway/estimated"),
    usage_kind: Optional[str] = Query(None, description="normal/compaction/subagent"),
    model: Optional[str] = Query(None),
    owner_type: Optional[str] = Query(None, description="usr/cus"),
    owner_id: Optional[int] = Query(None),
    client_id: Optional[str] = Query(None),
    session_no: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO 时间，含"),
    date_to: Optional[str] = Query(None, description="ISO 时间，含"),
    admin_id: int = require_superuser(),
):
    data = await HarnessDashboardService.usage_overview(
        source=source, usage_kind=usage_kind, model=model,
        owner_type=owner_type, owner_id=owner_id,
        client_id=client_id, session_no=session_no,
        date_from=_parse_dt(date_from), date_to=_parse_dt(date_to),
    )
    return success_response(data=data)


@dashboard_router.get("/runs/{run_no}/usage", summary="运行用量汇总")
async def run_usage(run_no: str, admin_id: int = require_superuser()):
    data = await HarnessDashboardService.run_usage(run_no)
    if data.get("error"):
        return fail_response(msg="运行不存在", code=404, status_code=404)
    return success_response(data=data)


@dashboard_router.get("/sessions/{session_no}/usage", summary="会话用量汇总")
async def session_usage(session_no: str, admin_id: int = require_superuser()):
    data = await HarnessDashboardService.session_usage(session_no)
    if data.get("error"):
        return fail_response(msg="会话不存在", code=404, status_code=404)
    return success_response(data=data)


@dashboard_router.post("/reconcile", summary="预占对账（释放超期与终态遗留）")
async def reconcile(
    release_expired: bool = Query(True, description="释放超期预占"),
    release_terminal_runs: bool = Query(True, description="释放终态 run 遗留预占"),
    admin_id: int = require_superuser(),
):
    data = await HarnessDashboardService.reconcile(
        release_expired=release_expired,
        release_terminal_runs=release_terminal_runs,
    )
    return success_response(data=data, msg="对账完成")


@dashboard_router.get("/anomalies", summary="异常明细")
async def anomalies(
    limit: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    data = await HarnessDashboardService.anomalies(limit=limit)
    return success_response(data=data)


# ==================== 网关记账 vs 客户端上报对账 ====================

@dashboard_router.post("/reconcile/gateway", summary="执行网关记账与客户端上报对账")
async def run_gateway_reconcile(
    window_start: Optional[str] = Query(None, description="窗口开始 ISO，含"),
    window_end: Optional[str] = Query(None, description="窗口结束 ISO，不含"),
    trigger: str = Query("manual", description="manual/scheduled"),
    admin_id: int = require_superuser(),
):
    data = await HarnessReconcileService.execute(
        window_start=_parse_dt(window_start),
        window_end=_parse_dt(window_end),
        trigger=trigger,
        operator_id=admin_id,
    )
    return success_response(data=data, msg="网关对账完成")


@dashboard_router.get("/reconcile/diffs", summary="网关对账差异列表")
async def list_reconcile_diffs(
    run_no: Optional[str] = Query(None),
    session_no: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    owner_type: Optional[str] = Query(None, description="usr/cus/org"),
    owner_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None, description="high/low"),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="open/resolved/ignored"),
    date_from: Optional[str] = Query(None, description="创建时间起，含"),
    date_to: Optional[str] = Query(None, description="创建时间止，含"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    data = await HarnessReconcileService.list_diffs(
        run_no=run_no, session_no=session_no, client_id=client_id,
        owner_type=owner_type, owner_id=owner_id,
        severity=severity, category=category, status=status,
        date_from=_parse_dt(date_from), date_to=_parse_dt(date_to),
        page=page, page_size=page_size,
    )
    return success_response(data=data)


@dashboard_router.get("/reconcile/diffs/{diff_id}", summary="网关对账差异明细")
async def reconcile_diff_detail(diff_id: int, admin_id: int = require_superuser()):
    data = await HarnessReconcileService.diff_detail(diff_id)
    if data.get("error"):
        return fail_response(msg="差异不存在", code=404, status_code=404)
    return success_response(data=data)


@dashboard_router.post("/reconcile/diffs/{diff_id}/resolve", summary="标记网关对账差异")
async def resolve_reconcile_diff(
    diff_id: int,
    status: str = Query("resolved", description="resolved/ignored/open"),
    note: Optional[str] = Query(None),
    admin_id: int = require_superuser(),
):
    data = await HarnessReconcileService.mark_diff(
        diff_id=diff_id, status=status, note=note, operator_id=admin_id,
    )
    if data.get("error") == "diff_not_found":
        return fail_response(msg="差异不存在", code=404, status_code=404)
    if data.get("error"):
        return fail_response(msg="状态非法（resolved/ignored/open）", code=400, status_code=400)
    return success_response(data=data, msg="已标记")


@dashboard_router.get("/reconcile/batches", summary="网关对账批次历史")
async def list_reconcile_batches(
    limit: int = Query(20, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    data = await HarnessReconcileService.list_batches(limit=limit)
    return success_response(data=data)


# ==================== 网关额度中断（预算/拒绝/截断/吊销） ====================

@dashboard_router.get("/gateway/quota", summary="网关租约额度看板（已用/剩余/预计请求数/拒绝截断）")
async def gateway_quota(
    client_id: Optional[str] = Query(None),
    owner_type: Optional[str] = Query(None, description="usr/cus/org"),
    owner_id: Optional[int] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    admin_id: int = require_superuser(),
):
    data = await GatewayBudgetService.list_dashboard(
        client_id=client_id,
        owner_type=owner_type,
        owner_id=owner_id,
        active_only=active_only,
        limit=limit,
    )
    return success_response(data=data)


@dashboard_router.post("/gateway/leases/{lease_id}/revoke", summary="手动吊销网关租约（应急止损）")
async def revoke_gateway_lease(
    lease_id: str,
    reason: str = Query("manual_emergency", description="吊销原因，写入审计"),
    admin_id: int = require_superuser(),
):
    try:
        data = await GatewayLeaseService.revoke_internal(
            lease_id,
            reason=reason,
            actor_type="user",
            actor_id=str(admin_id),
        )
    except HTTPException as exc:
        return fail_response(msg=str(exc.detail), code=exc.status_code, status_code=exc.status_code)
    return success_response(data=data, msg="租约已吊销")
