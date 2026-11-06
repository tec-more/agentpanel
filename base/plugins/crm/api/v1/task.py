from fastapi import APIRouter, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.crm.schemas.task_schema import FollowUpTaskCreate, FollowUpTaskUpdate, TaskListQuery, TaskCompleteRequest
from base.plugins.crm.services.follow_up_task_service import FollowUpTaskService

task_router = APIRouter(prefix="/tasks", tags=["跟进任务管理"])


@task_router.post("")
async def create_task(
    task_data: FollowUpTaskCreate,
    user_id: int = require_permission("crm:task:create"),
):
    try:
        task = await FollowUpTaskService.create_task(task_data, user_id)
        return success_response(data=await task.to_dict(), msg="任务创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@task_router.get("/mine")
async def get_my_tasks(
    user_id: int = Depends(get_current_user_id),
):
    tasks = await FollowUpTaskService.get_my_tasks(user_id)
    items = [await t.to_dict() for t in tasks]
    return success_response(data=items)


@task_router.get("")
async def get_task_list(
    query_params: TaskListQuery = Depends(),
    user_id: int = require_permission("crm:task:view"),
):
    tasks, total = await FollowUpTaskService.get_task_list(query_params, user_id)
    items = [await t.to_dict() for t in tasks]
    return success_response(data={"total": total, "page": query_params.page, "page_size": query_params.page_size, "items": items})


@task_router.put("/{task_id}")
async def update_task(
    task_id: int,
    task_data: FollowUpTaskUpdate,
    user_id: int = require_permission("crm:task:edit"),
):
    try:
        task = await FollowUpTaskService.update_task(task_id, task_data)
        if not task:
            return fail_response(msg="任务不存在", code=404)
        return success_response(data=await task.to_dict(), msg="任务更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@task_router.post("/{task_id}/complete")
async def complete_task(
    task_id: int,
    complete_data: TaskCompleteRequest,
    user_id: int = require_permission("crm:task:edit"),
):
    task = await FollowUpTaskService.complete_task(task_id, complete_data, user_id)
    if not task:
        return fail_response(msg="任务不存在", code=404)
    return success_response(data=await task.to_dict(), msg="任务完成成功")


@task_router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    user_id: int = require_permission("crm:task:edit"),
):
    task = await FollowUpTaskService.cancel_task(task_id)
    if not task:
        return fail_response(msg="任务不存在", code=404)
    return success_response(data=await task.to_dict(), msg="任务取消成功")