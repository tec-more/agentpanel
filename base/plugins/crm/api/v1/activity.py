from fastapi import APIRouter, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.crm.schemas.activity_schema import ActivityCreate, ActivityListQuery, TimelineQuery
from base.plugins.crm.services.activity_service import ActivityService

activity_router = APIRouter(prefix="/activities", tags=["活动管理"])


@activity_router.post("")
async def create_activity(
    activity_data: ActivityCreate,
    user_id: int = require_permission("crm:activity:create"),
):
    try:
        activity = await ActivityService.create_activity(activity_data, user_id)
        return success_response(data=await activity.to_dict(), msg="活动创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@activity_router.get("/timeline")
async def get_timeline(
    query_params: TimelineQuery = Depends(),
    user_id: int = require_permission("crm:activity:view"),
):
    try:
        activities, total = await ActivityService.get_timeline(query_params, user_id)
        items = [await a.to_dict() for a in activities]
        return success_response(data={"total": total, "page": query_params.page, "page_size": query_params.page_size, "items": items})
    except ValueError as e:
        return fail_response(msg=str(e))


@activity_router.get("")
async def get_activity_list(
    query_params: ActivityListQuery = Depends(),
    user_id: int = require_permission("crm:activity:view"),
):
    activities, total = await ActivityService.get_activity_list(query_params, user_id)
    items = [await a.to_dict() for a in activities]
    return success_response(data={"total": total, "page": query_params.page, "page_size": query_params.page_size, "items": items})


@activity_router.delete("/{activity_id}")
async def delete_activity(
    activity_id: int,
    user_id: int = require_permission("crm:activity:delete"),
):
    result = await ActivityService.delete_activity(activity_id)
    if not result:
        return fail_response(msg="活动不存在", code=404)
    return success_response(msg="活动删除成功")