from fastapi import APIRouter, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import SuccessResponse, ErrorResponse, success_response, fail_response
from base.plugins.crm.schemas.lead_schema import LeadCreate, LeadUpdate, LeadListQuery, LeadConvertRequest, LeadAssignRequest
from base.plugins.crm.services.lead_service import LeadService

lead_router = APIRouter(prefix="/leads", tags=["线索管理"])


@lead_router.post("")
async def create_lead(
    lead_data: LeadCreate,
    user_id: int = require_permission("crm:lead:create"),
):
    try:
        lead = await LeadService.create_lead(lead_data, user_id)
        return success_response(data=await lead.to_dict(), msg="线索创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@lead_router.get("")
async def get_lead_list(
    query_params: LeadListQuery = Depends(),
    user_id: int = require_permission("crm:lead:view"),
):
    leads, total = await LeadService.get_lead_list(query_params, user_id)
    items = [await lead.to_dict() for lead in leads]
    return success_response(data={"total": total, "page": query_params.page, "page_size": query_params.page_size, "items": items})


@lead_router.get("/{lead_id}")
async def get_lead_by_id(
    lead_id: int,
    user_id: int = require_permission("crm:lead:view"),
):
    lead = await LeadService.get_lead_by_id(lead_id)
    if not lead:
        return fail_response(msg="线索不存在", code=404)
    return success_response(data=await lead.to_dict())


@lead_router.put("/{lead_id}")
async def update_lead(
    lead_id: int,
    lead_data: LeadUpdate,
    user_id: int = require_permission("crm:lead:edit"),
):
    try:
        lead = await LeadService.update_lead(lead_id, lead_data)
        if not lead:
            return fail_response(msg="线索不存在", code=404)
        return success_response(data=await lead.to_dict(), msg="线索更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@lead_router.delete("/{lead_id}")
async def delete_lead(
    lead_id: int,
    user_id: int = require_permission("crm:lead:delete"),
):
    try:
        result = await LeadService.delete_lead(lead_id)
        if not result:
            return fail_response(msg="线索不存在", code=404)
        return success_response(msg="线索删除成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@lead_router.post("/{lead_id}/convert")
async def convert_lead(
    lead_id: int,
    user_id: int = require_permission("crm:lead:convert"),
):
    try:
        lead = await LeadService.convert_lead(lead_id, user_id)
        return success_response(data=await lead.to_dict(), msg="线索转化成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@lead_router.post("/{lead_id}/assign")
async def assign_lead(
    lead_id: int,
    assign_data: LeadAssignRequest,
    user_id: int = require_permission("crm:lead:assign"),
):
    lead = await LeadService.assign_lead(lead_id, assign_data.assigned_to)
    if not lead:
        return fail_response(msg="线索不存在", code=404)
    return success_response(data=await lead.to_dict(), msg="线索分配成功")