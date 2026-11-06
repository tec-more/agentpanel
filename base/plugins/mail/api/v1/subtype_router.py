"""
消息子类型 API 路由
"""
from fastapi import APIRouter, Query
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.mail.schemas.subtype_schema import SubtypeCreate, SubtypeUpdate, SubtypeListQuery
from base.plugins.mail.services.subtype_service import SubtypeService

subtype_router = APIRouter(prefix="/subtypes", tags=["消息-子类型"])


@subtype_router.get("")
async def list_subtypes(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    model: str = None,
    is_active: bool = None,
    keyword: str = None,
    user_id: int = require_permission("mail:subtype:view"),
):
    """获取子类型列表"""
    query = SubtypeListQuery(
        page=page, page_size=page_size,
        model=model, is_active=is_active, keyword=keyword,
    )
    data = await SubtypeService.list_subtypes(query)
    return success_response(data=data)


@subtype_router.get("/{subtype_id}")
async def get_subtype(
    subtype_id: int,
    user_id: int = require_permission("mail:subtype:view"),
):
    """获取子类型详情"""
    subtype = await SubtypeService.get_subtype(subtype_id)
    if not subtype:
        return fail_response(msg="子类型不存在", code=404)
    return success_response(data=await subtype.to_dict())


@subtype_router.post("")
async def create_subtype(
    payload: SubtypeCreate,
    user_id: int = require_permission("mail:subtype:manage"),
):
    """创建子类型"""
    try:
        subtype = await SubtypeService.create_subtype(payload)
    except ValueError as e:
        return fail_response(msg=str(e))
    return success_response(data=await subtype.to_dict(), msg="子类型创建成功")


@subtype_router.put("/{subtype_id}")
async def update_subtype(
    subtype_id: int,
    payload: SubtypeUpdate,
    user_id: int = require_permission("mail:subtype:manage"),
):
    """更新子类型"""
    try:
        subtype = await SubtypeService.update_subtype(subtype_id, payload)
    except ValueError as e:
        return fail_response(msg=str(e))
    if not subtype:
        return fail_response(msg="子类型不存在", code=404)
    return success_response(data=await subtype.to_dict(), msg="子类型更新成功")


@subtype_router.delete("/{subtype_id}")
async def delete_subtype(
    subtype_id: int,
    user_id: int = require_permission("mail:subtype:manage"),
):
    """删除子类型（系统预设禁止删除）"""
    try:
        success = await SubtypeService.delete_subtype(subtype_id)
    except ValueError as e:
        return fail_response(msg=str(e))
    if not success:
        return fail_response(msg="子类型不存在", code=404)
    return success_response(msg="子类型删除成功")
