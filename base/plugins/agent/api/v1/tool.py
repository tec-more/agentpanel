"""
Tool API routes
"""
from fastapi import APIRouter
from base.plugins.agent.schemas.tool import ToolCreate, ToolUpdate, ToolResponse
from base.plugins.agent.services.tool_service import ToolService
from base.common.response import success_response, fail_response

tool_router = APIRouter(prefix="/tools", tags=["tools"])


@tool_router.post("/")
async def create_tool(tool: ToolCreate):
    """Create a new tool"""
    existing = await ToolService.get_tool_by_name(tool.name)
    if existing:
        return fail_response(msg="工具标识已存在")
    
    created_tool = await ToolService.create_tool(tool)
    if not created_tool:
        return fail_response(msg="创建工具失败")
    
    data = ToolResponse.model_validate(created_tool)
    return success_response(data=data.model_dump(), msg="工具创建成功")


@tool_router.get("/")
async def get_tools(skip: int = 0, limit: int = 100, name: str = "", enabled: bool = None):
    """Get all tools"""
    tools = await ToolService.get_tools(skip=skip, limit=limit, name=name, enabled=enabled)
    
    total = await ToolService.get_tools(name=name, enabled=enabled)
    total_count = len(total)
    
    data = [ToolResponse.model_validate(t).model_dump() for t in tools]
    return success_response(data={"items": data, "total": total_count})


@tool_router.get("/{tool_id}")
async def get_tool(tool_id: int):
    """Get tool by ID"""
    tool = await ToolService.get_tool_by_id(tool_id)
    if not tool:
        return fail_response(msg="工具不存在", code=404)
    
    data = ToolResponse.model_validate(tool)
    return success_response(data=data.model_dump())


@tool_router.put("/{tool_id}")
async def update_tool(tool_id: int, tool: ToolUpdate):
    """Update tool"""
    updated_tool = await ToolService.update_tool(tool_id, tool)
    if not updated_tool:
        return fail_response(msg="工具不存在", code=404)
    
    data = ToolResponse.model_validate(updated_tool)
    return success_response(data=data.model_dump(), msg="工具更新成功")


@tool_router.delete("/{tool_id}")
async def delete_tool(tool_id: int):
    """Delete tool"""
    success = await ToolService.delete_tool(tool_id)
    if not success:
        return fail_response(msg="工具不存在", code=404)
    return success_response(msg="工具删除成功")


@tool_router.get("/active/list")
async def get_active_tools():
    """Get active tools"""
    tools = await ToolService.get_active_tools()
    data = [ToolResponse.model_validate(t).model_dump() for t in tools]
    return success_response(data=data)
