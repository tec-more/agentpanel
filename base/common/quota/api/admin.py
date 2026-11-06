"""
M9 套餐管理 API：/v1/quota-plans（CRUD + 绑定关系管理）

溯源：docs/arch/04 §2.2 GET/POST/PUT/DELETE /v1/quota-plans（套餐 CRUD，绑定会员等级/角色）。
鉴权：require_superuser（沿用 T3 管理侧惯例）。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from base.common.permissions import require_superuser
from base.common.response import fail_response, success_response
from base.common.quota.services.plan_service import PlanService

quota_plan_admin_router = APIRouter(prefix="/v1/quota-plans", tags=["配额套餐管理"])


class PlanUpsertSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="套餐编码（唯一）")
    name: str = Field(..., min_length=1, max_length=100, description="套餐名称")
    scope: str = Field("both", description="适用范围: cus/usr/both")
    quota_items: Dict[str, Any] = Field(default_factory=dict, description="配额项定义")
    status: str = Field("active", description="状态: active/disabled")


class PlanUpdateSchema(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    scope: Optional[str] = None
    quota_items: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class BindingSchema(BaseModel):
    bind_type: str = Field(..., description="绑定类型: membership_level/role")
    bind_key: str = Field(..., min_length=1, max_length=50, description="会员等级 level_type 或角色 code")
    plan_id: int = Field(..., gt=0, description="套餐 ID")
    priority: int = Field(0, description="优先级（数值大者优先）")


@quota_plan_admin_router.get("", summary="套餐列表")
async def list_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    admin_id: int = require_superuser(),
):
    data = await PlanService.list_plans(page=page, page_size=page_size, status=status, scope=scope)
    return success_response(data=data)


@quota_plan_admin_router.post("", summary="创建套餐")
async def create_plan(data: PlanUpsertSchema, admin_id: int = require_superuser()):
    try:
        plan = await PlanService.create_plan(data.model_dump())
        return success_response(data=PlanService.plan_to_dict(plan), msg="创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@quota_plan_admin_router.get("/bindings", summary="绑定关系列表")
async def list_bindings(
    bind_type: Optional[str] = Query(None, description="membership_level/role"),
    admin_id: int = require_superuser(),
):
    data = await PlanService.list_bindings(bind_type=bind_type)
    return success_response(data={"items": data, "total": len(data)})


@quota_plan_admin_router.post("/bindings", summary="创建/更新绑定")
async def create_binding(data: BindingSchema, admin_id: int = require_superuser()):
    try:
        binding = await PlanService.bind(
            bind_type=data.bind_type, bind_key=data.bind_key,
            plan_id=data.plan_id, priority=data.priority,
        )
        return success_response(data={"id": binding.id}, msg="绑定成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@quota_plan_admin_router.delete("/bindings/{binding_id}", summary="删除绑定")
async def delete_binding(binding_id: int, admin_id: int = require_superuser()):
    ok = await PlanService.unbind(binding_id)
    if not ok:
        return fail_response(msg="绑定不存在", status_code=404)
    return success_response(msg="已删除")


@quota_plan_admin_router.get("/{plan_id}", summary="套餐详情")
async def get_plan(plan_id: int, admin_id: int = require_superuser()):
    plan = await PlanService.get_plan(plan_id)
    if plan is None:
        return fail_response(msg="套餐不存在", status_code=404)
    return success_response(data=PlanService.plan_to_dict(plan))


@quota_plan_admin_router.put("/{plan_id}", summary="更新套餐")
async def update_plan(plan_id: int, data: PlanUpdateSchema, admin_id: int = require_superuser()):
    try:
        plan = await PlanService.update_plan(
            plan_id, {k: v for k, v in data.model_dump().items() if v is not None}
        )
        if plan is None:
            return fail_response(msg="套餐不存在", status_code=404)
        return success_response(data=PlanService.plan_to_dict(plan), msg="更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@quota_plan_admin_router.delete("/{plan_id}", summary="删除套餐")
async def delete_plan(plan_id: int, admin_id: int = require_superuser()):
    ok = await PlanService.delete_plan(plan_id)
    if not ok:
        return fail_response(msg="套餐不存在", status_code=404)
    return success_response(msg="已删除")
