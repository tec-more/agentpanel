from fastapi import APIRouter, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.crm.schemas.opportunity_schema import (
    OpportunityCreate, OpportunityUpdate, OpportunityListQuery,
    OpportunityAdvanceRequest, OpportunityWinRequest, OpportunityLoseRequest,
)
from base.plugins.crm.services.opportunity_service import OpportunityService

opportunity_router = APIRouter(prefix="/opportunities", tags=["商机管理"])


@opportunity_router.post("")
async def create_opportunity(
    opp_data: OpportunityCreate,
    user_id: int = require_permission("crm:opportunity:create"),
):
    try:
        opp = await OpportunityService.create_opportunity(opp_data, user_id)
        return success_response(data=await opp.to_dict(), msg="商机创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@opportunity_router.get("/kanban")
async def get_kanban_view(
    user_id: int = require_permission("crm:opportunity:view"),
):
    result = await OpportunityService.get_kanban_view(user_id)
    return success_response(data=result)


@opportunity_router.get("")
async def get_opportunity_list(
    query_params: OpportunityListQuery = Depends(),
    user_id: int = require_permission("crm:opportunity:view"),
):
    opps, total = await OpportunityService.get_opportunity_list(query_params, user_id)
    items = [await opp.to_dict() for opp in opps]
    return success_response(data={"total": total, "page": query_params.page, "page_size": query_params.page_size, "items": items})


@opportunity_router.get("/{opportunity_id}")
async def get_opportunity_by_id(
    opportunity_id: int,
    user_id: int = require_permission("crm:opportunity:view"),
):
    opp = await OpportunityService.get_opportunity_by_id(opportunity_id)
    if not opp:
        return fail_response(msg="商机不存在", code=404)
    return success_response(data=opp)


@opportunity_router.put("/{opportunity_id}")
async def update_opportunity(
    opportunity_id: int,
    opp_data: OpportunityUpdate,
    user_id: int = require_permission("crm:opportunity:edit"),
):
    try:
        opp = await OpportunityService.update_opportunity(opportunity_id, opp_data)
        if not opp:
            return fail_response(msg="商机不存在", code=404)
        return success_response(data=await opp.to_dict(), msg="商机更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@opportunity_router.delete("/{opportunity_id}")
async def delete_opportunity(
    opportunity_id: int,
    user_id: int = require_permission("crm:opportunity:delete"),
):
    try:
        result = await OpportunityService.delete_opportunity(opportunity_id)
        if not result:
            return fail_response(msg="商机不存在", code=404)
        return success_response(msg="商机删除成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@opportunity_router.post("/{opportunity_id}/advance")
async def advance_stage(
    opportunity_id: int,
    advance_data: OpportunityAdvanceRequest,
    user_id: int = require_permission("crm:opportunity:edit"),
):
    try:
        opp = await OpportunityService.advance_stage(opportunity_id, advance_data, user_id)
        if not opp:
            return fail_response(msg="商机不存在", code=404)
        return success_response(data=await opp.to_dict(), msg="商机阶段推进成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@opportunity_router.post("/{opportunity_id}/win")
async def mark_won(
    opportunity_id: int,
    win_data: OpportunityWinRequest,
    user_id: int = require_permission("crm:opportunity:edit"),
):
    try:
        opp = await OpportunityService.mark_won(opportunity_id, win_data, user_id)
        if not opp:
            return fail_response(msg="商机不存在", code=404)
        return success_response(data=await opp.to_dict(), msg="商机标记赢单成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@opportunity_router.post("/{opportunity_id}/lose")
async def mark_lost(
    opportunity_id: int,
    lose_data: OpportunityLoseRequest,
    user_id: int = require_permission("crm:opportunity:edit"),
):
    try:
        opp = await OpportunityService.mark_lost(opportunity_id, lose_data, user_id)
        if not opp:
            return fail_response(msg="商机不存在", code=404)
        return success_response(data=await opp.to_dict(), msg="商机标记输单成功")
    except ValueError as e:
        return fail_response(msg=str(e))