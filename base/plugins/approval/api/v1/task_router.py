"""
审批任务 API 路由
"""
from fastapi import APIRouter, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.approval.schemas.task_schema import TaskApprove, TaskReject, TaskTransfer
from base.plugins.approval.services.task_service import TaskService

task_router = APIRouter(prefix="/tasks", tags=["审批任务"])


@task_router.get("/my")
async def get_my_tasks(
    status: str = "pending",
    page: int = 1,
    page_size: int = 10,
    user_id: int = require_permission("approval:center:view"),
):
    """获取我的审批任务"""
    result = await TaskService.get_my_tasks(user_id, status, page, page_size)
    return success_response(data=result)


@task_router.get("/{task_id}")
async def get_task_detail(
    task_id: int,
    user_id: int = require_permission("approval:center:view"),
):
    """获取任务详情"""
    task = await TaskService.get_task_detail(task_id)
    if not task:
        return fail_response(msg="任务不存在", code=404)
    return success_response(data=task)


@task_router.post("/{task_id}/approve")
async def approve_task(
    task_id: int,
    data: TaskApprove,
    user_id: int = require_permission("approval:task:handle"),
):
    """审批通过/拒绝"""
    try:
        result = await TaskService.approve_task(
            task_id, user_id, data.comment, data.approved
        )
        return success_response(data=result, msg="审批成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@task_router.post("/{task_id}/transfer")
async def transfer_task(
    task_id: int,
    data: TaskTransfer,
    user_id: int = require_permission("approval:task:handle"),
):
    """转审任务"""
    try:
        result = await TaskService.transfer_task(
            task_id, user_id, data.transfer_to, data.comment
        )
        return success_response(data=result, msg="转审成功")
    except ValueError as e:
        return fail_response(msg=str(e))
