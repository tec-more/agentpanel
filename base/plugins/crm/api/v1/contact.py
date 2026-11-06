from fastapi import APIRouter, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.crm.schemas.contact_schema import ContactCreate, ContactUpdate, ContactListQuery
from base.plugins.crm.services.contact_service import ContactService

contact_router = APIRouter(prefix="/contacts", tags=["联系人管理"])


@contact_router.post("")
async def create_contact(
    contact_data: ContactCreate,
    user_id: int = require_permission("crm:contact:create"),
):
    try:
        contact = await ContactService.create_contact(contact_data)
        return success_response(data=await contact.to_dict(), msg="联系人创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@contact_router.get("")
async def get_contact_list(
    query_params: ContactListQuery = Depends(),
    user_id: int = require_permission("crm:contact:view"),
):
    contacts, total = await ContactService.get_contact_list(query_params, user_id)
    items = [await c.to_dict() for c in contacts]
    return success_response(data={"total": total, "page": query_params.page, "page_size": query_params.page_size, "items": items})


@contact_router.put("/{contact_id}")
async def update_contact(
    contact_id: int,
    contact_data: ContactUpdate,
    user_id: int = require_permission("crm:contact:edit"),
):
    try:
        contact = await ContactService.update_contact(contact_id, contact_data)
        if not contact:
            return fail_response(msg="联系人不存在", code=404)
        return success_response(data=await contact.to_dict(), msg="联系人更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@contact_router.delete("/{contact_id}")
async def delete_contact(
    contact_id: int,
    user_id: int = require_permission("crm:contact:delete"),
):
    try:
        result = await ContactService.delete_contact(contact_id)
        if not result:
            return fail_response(msg="联系人不存在", code=404)
        return success_response(msg="联系人删除成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@contact_router.post("/{contact_id}/set-primary")
async def set_primary(
    contact_id: int,
    user_id: int = require_permission("crm:contact:edit"),
):
    contact = await ContactService.set_primary(contact_id)
    if not contact:
        return fail_response(msg="联系人不存在", code=404)
    return success_response(data=await contact.to_dict(), msg="主联系人设置成功")