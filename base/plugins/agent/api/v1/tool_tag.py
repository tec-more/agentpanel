"""
Tool Tag API routes
"""
from typing import List
from fastapi import APIRouter
from base.plugins.agent.schemas.tool_tag import ToolTagCreate, ToolTagUpdate, ToolTagResponse
from base.plugins.agent.services.tool_tag_service import ToolTagService
from base.common.response import success_response, fail_response

tool_tag_router = APIRouter(prefix="/tool-tags", tags=["tool-tags"])


@tool_tag_router.post("/")
async def create_tag(tag: ToolTagCreate):
    """Create a new tag"""
    existing = await ToolTagService.get_tag_by_name(tag.name)
    if existing:
        return fail_response(msg="标签名称已存在")
    
    created_tag = await ToolTagService.create_tag(tag)
    if not created_tag:
        return fail_response(msg="创建标签失败")
    
    data = ToolTagResponse.model_validate(created_tag)
    return success_response(data=data.model_dump(), msg="标签创建成功")


@tool_tag_router.get("/")
async def get_tags(skip: int = 0, limit: int = 100, name: str = "", enabled: bool = None):
    """Get all tags"""
    tags = await ToolTagService.get_tags(skip=skip, limit=limit, name=name, enabled=enabled)
    total = await ToolTagService.get_tags(name=name, enabled=enabled)
    total_count = len(total)
    
    data = [ToolTagResponse.model_validate(t).model_dump() for t in tags]
    return success_response(data={"items": data, "total": total_count})


@tool_tag_router.get("/with-count")
async def get_tags_with_count():
    """Get tags with tool count"""
    tags = await ToolTagService.get_tags_with_count()
    return success_response(data=tags)


@tool_tag_router.get("/{tag_id}")
async def get_tag(tag_id: int):
    """Get tag by ID"""
    tag = await ToolTagService.get_tag_by_id(tag_id)
    if not tag:
        return fail_response(msg="标签不存在", code=404)
    
    data = ToolTagResponse.model_validate(tag)
    return success_response(data=data.model_dump())


@tool_tag_router.put("/{tag_id}")
async def update_tag(tag_id: int, tag: ToolTagUpdate):
    """Update tag"""
    updated_tag = await ToolTagService.update_tag(tag_id, tag)
    if not updated_tag:
        return fail_response(msg="标签不存在", code=404)
    
    data = ToolTagResponse.model_validate(updated_tag)
    return success_response(data=data.model_dump(), msg="标签更新成功")


@tool_tag_router.delete("/{tag_id}")
async def delete_tag(tag_id: int):
    """Delete tag"""
    success = await ToolTagService.delete_tag(tag_id)
    if not success:
        return fail_response(msg="标签不存在", code=404)
    return success_response(msg="标签删除成功")


@tool_tag_router.get("/active/list")
async def get_active_tags():
    """Get active tags"""
    tags = await ToolTagService.get_active_tags()
    data = [ToolTagResponse.model_validate(t).model_dump() for t in tags]
    return success_response(data=data)
