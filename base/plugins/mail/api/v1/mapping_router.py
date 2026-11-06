"""
事件→消息映射 API 路由
"""
from fastapi import APIRouter, Query
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.mail.schemas.mapping_schema import MappingCreate, MappingUpdate, MappingListQuery
from base.plugins.mail.services.mapping_service import MappingService

mapping_router = APIRouter(prefix="/mappings", tags=["消息-事件映射"])


@mapping_router.get("")
async def list_mappings(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    model: str = None,
    action: str = None,
    is_active: bool = None,
    user_id: int = require_permission("mail:mapping:view"),
):
    """获取映射列表"""
    query = MappingListQuery(
        page=page, page_size=page_size,
        model=model, action=action, is_active=is_active,
    )
    data = await MappingService.list_mappings(query)
    return success_response(data=data)


@mapping_router.get("/{mapping_id}")
async def get_mapping(
    mapping_id: int,
    user_id: int = require_permission("mail:mapping:view"),
):
    """获取映射详情"""
    m = await MappingService.get_mapping(mapping_id)
    if not m:
        return fail_response(msg="映射不存在", code=404)
    return success_response(data=await m.to_dict(include_subtype=True))


@mapping_router.post("")
async def create_mapping(
    payload: MappingCreate,
    user_id: int = require_permission("mail:mapping:manage"),
):
    """创建映射"""
    try:
        m = await MappingService.create_mapping(payload)
    except ValueError as e:
        return fail_response(msg=str(e))
    return success_response(data=await m.to_dict(include_subtype=True), msg="映射创建成功")


@mapping_router.put("/{mapping_id}")
async def update_mapping(
    mapping_id: int,
    payload: MappingUpdate,
    user_id: int = require_permission("mail:mapping:manage"),
):
    """更新映射"""
    try:
        m = await MappingService.update_mapping(mapping_id, payload)
    except ValueError as e:
        return fail_response(msg=str(e))
    if not m:
        return fail_response(msg="映射不存在", code=404)
    return success_response(data=await m.to_dict(include_subtype=True), msg="映射更新成功")


@mapping_router.delete("/{mapping_id}")
async def delete_mapping(
    mapping_id: int,
    user_id: int = require_permission("mail:mapping:manage"),
):
    """删除映射"""
    success = await MappingService.delete_mapping(mapping_id)
    if not success:
        return fail_response(msg="映射不存在", code=404)
    return success_response(msg="映射删除成功")
