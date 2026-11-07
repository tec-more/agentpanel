"""
P3 组织级配额管理 API：/v1/quota/organizations

溯源：01-需求与约束.md P3（组织维度配额计划与账户、看板按组织拆分）
鉴权：
- 读接口 quota:org:view / quota:org:manage
- 操作接口 quota:org:manage
- 非管理员仅能访问自己关联客户所属组织，越权返回 403（不是空列表）
实现：复用 QuotaService / QuotaReservation 同一套账，不新建并行账本。
"""
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from base.common.permissions import require_any_permission, require_permission
from base.common.quota.services.org_quota_service import OrgQuotaError, OrgQuotaService
from base.common.quota.services.org_scope import ensure_org_access, resolve_user_org_ids
from base.common.response import fail_response, success_response

org_quota_admin_router = APIRouter(prefix="/v1/quota/organizations", tags=["组织配额管理"])

_view_access = require_any_permission("quota:org:view", "quota:org:manage")
_manage_access = require_permission("quota:org:manage")

_STATUS_MAP = {
    "not_found": 404,
    "plugin_disabled": 503,
    "org_disabled": 409,
    "invalid_plan": 400,
    "invalid_status": 400,
}


def _fail(e: OrgQuotaError):
    return fail_response(msg=e.message, status_code=_STATUS_MAP.get(e.code, 400))


class AssignPlanSchema(BaseModel):
    plan_id: int = Field(..., gt=0, description="组织可用的配额套餐 ID（scope=org/both）")
    priority: int = Field(0, description="优先级（数值大者优先，调整时覆盖）")


class AccountStatusSchema(BaseModel):
    status: str = Field(..., description="账户状态: active/frozen")


@org_quota_admin_router.get("", summary="组织配额账户列表")
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="组织状态: active/disabled"),
    keyword: Optional[str] = Query(None, description="组织名称模糊搜索"),
    plan_code: Optional[str] = Query(None, description="按套餐编码过滤"),
    has_stale_hold: Optional[bool] = Query(None, description="是否存在超期预占"),
    near_limit: Optional[bool] = Query(None, description="是否接近上限（>=80%）"),
    user_id: int = _view_access,
):
    org_ids = await resolve_user_org_ids(user_id)
    data = await OrgQuotaService.list_organizations(
        page=page, page_size=page_size, status=status,
        keyword=keyword, plan_code=plan_code,
        has_stale_hold=has_stale_hold, near_limit=near_limit,
        org_ids=list(org_ids) if org_ids is not None else None,
    )
    return success_response(data=data)


@org_quota_admin_router.get("/plans/available", summary="组织可分配套餐列表")
async def list_available_plans(user_id: int = _view_access):
    return success_response(data=await OrgQuotaService.available_plans())


@org_quota_admin_router.get("/{org_id}", summary="组织配额详情")
async def get_organization_detail(org_id: int, user_id: int = _view_access):
    await ensure_org_access(user_id, org_id)
    try:
        data = await OrgQuotaService.get_detail(org_id)
        return success_response(data=data)
    except OrgQuotaError as e:
        return _fail(e)


@org_quota_admin_router.post("/{org_id}/plan", summary="分配/调整组织套餐")
async def assign_plan(
    org_id: int, data: AssignPlanSchema, user_id: int = _manage_access,
):
    await ensure_org_access(user_id, org_id)
    try:
        result = await OrgQuotaService.assign_plan(org_id, data.plan_id, data.priority)
        return success_response(data=result, msg="分配成功")
    except OrgQuotaError as e:
        return _fail(e)


@org_quota_admin_router.delete("/{org_id}/plan", summary="解绑组织套餐")
async def unbind_plan(org_id: int, user_id: int = _manage_access):
    await ensure_org_access(user_id, org_id)
    try:
        result = await OrgQuotaService.unbind_plan(org_id)
        return success_response(data=result, msg="已解绑")
    except OrgQuotaError as e:
        return _fail(e)


@org_quota_admin_router.post("/{org_id}/status", summary="启用/停用组织配额账户")
async def set_account_status(
    org_id: int, data: AccountStatusSchema, user_id: int = _manage_access,
):
    await ensure_org_access(user_id, org_id)
    try:
        result = await OrgQuotaService.set_account_status(org_id, data.status)
        return success_response(data=result, msg="状态已更新")
    except OrgQuotaError as e:
        return _fail(e)


@org_quota_admin_router.get("/{org_id}/board", summary="组织配额看板")
async def get_organization_board(
    org_id: int,
    days: int = Query(0, ge=0, le=400, description="统计窗口天数；0=当前自然月"),
    user_id: int = _view_access,
):
    await ensure_org_access(user_id, org_id)
    try:
        data = await OrgQuotaService.board(org_id, days=days)
        return success_response(data=data)
    except OrgQuotaError as e:
        return _fail(e)
