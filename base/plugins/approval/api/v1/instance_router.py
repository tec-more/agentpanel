"""
审批实例 API 路由
"""
from fastapi import APIRouter, Depends
from base.common.security import get_current_user_id
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.approval.schemas.instance_schema import InstanceCreate, InstanceListQuery
from base.plugins.approval.services.instance_service import InstanceService

instance_router = APIRouter(prefix="/instances", tags=["审批实例"])


@instance_router.post("")
async def create_instance(
    data: InstanceCreate,
    user_id: int = require_permission("approval:center:view"),
):
    """发起审批"""
    try:
        instance = await InstanceService.create_instance(data, user_id)
        return success_response(data=await instance.to_dict(), msg="审批发起成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@instance_router.get("")
async def get_instance_list(
    page: int = 1,
    page_size: int = 10,
    status: str = None,
    business_type: str = None,
    title: str = None,
    scope: str = None,
    user_id: int = require_permission("approval:center:view"),
):
    """获取审批实例列表"""
    query = InstanceListQuery(
        page=page,
        page_size=page_size,
        status=status,
        business_type=business_type,
        title=title
    )
    result = await InstanceService.get_instance_list(query, user_id, scope)
    return success_response(data=result)


@instance_router.get("/{instance_id}")
async def get_instance_detail(
    instance_id: int,
    user_id: int = require_permission("approval:center:view"),
):
    """获取审批实例详情"""
    progress = await InstanceService.get_instance_progress(instance_id)
    if not progress:
        return fail_response(msg="实例不存在", code=404)
    return success_response(data=progress)


@instance_router.post("/{instance_id}/cancel")
async def cancel_instance(
    instance_id: int,
    user_id: int = require_permission("approval:center:view"),
):
    """撤销审批"""
    try:
        instance = await InstanceService.cancel_instance(instance_id, user_id)
        if not instance:
            return fail_response(msg="实例不存在", code=404)
        return success_response(data=await instance.to_dict(), msg="撤销成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@instance_router.get("/business/{business_type}/{business_id}")
async def get_instance_by_business(
    business_type: str,
    business_id: int,
    user_id: int = require_permission("approval:center:view"),
):
    """根据业务信息获取审批实例"""
    from base.plugins.approval.models.approval_instance import ApprovalInstance
    instance = await ApprovalInstance.get_or_none(
        business_type=business_type,
        business_id=business_id
    )
    if not instance:
        return success_response(data=None, msg="未找到审批记录")
    return success_response(data=await instance.to_dict())
