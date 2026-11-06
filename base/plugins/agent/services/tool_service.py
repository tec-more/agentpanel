"""
Tool service
"""
from typing import List, Optional
from tortoise.exceptions import DoesNotExist, IntegrityError
from base.plugins.agent.models.tool import Tool
from base.plugins.agent.schemas.tool import ToolCreate, ToolUpdate
class ToolService:
    model = "tool"
    """Tool service class"""

    @staticmethod
    async def create_tool(tool_data: ToolCreate) -> Optional[Tool]:
        """Create tool"""
        try:
            tool = await Tool.create(
                name=tool_data.name,
                display_name=tool_data.display_name,
                description=tool_data.description,
                func_path=tool_data.func_path,
                parameters=tool_data.parameters,
                enabled=tool_data.enabled
            )
            return tool
        except IntegrityError:
            return None

    @staticmethod
    async def get_tools(skip: int = 0, limit: int = 100, name: str = "", enabled: bool = None) -> List[Tool]:
        """Get tool list"""
        query = Tool.all()
        if name:
            query = query.filter(name__icontains=name)
        if enabled is not None:
            query = query.filter(enabled=enabled)
        tools = await query.offset(skip).limit(limit)
        return tools

    @staticmethod
    async def get_tool_by_id(tool_id: int) -> Optional[Tool]:
        """Get tool by ID"""
        try:
            tool = await Tool.get(id=tool_id)
            return tool
        except DoesNotExist:
            return None

    @staticmethod
    async def get_tool_by_name(name: str) -> Optional[Tool]:
        """Get tool by name"""
        try:
            tool = await Tool.get(name=name)
            return tool
        except DoesNotExist:
            return None

    @staticmethod
    async def update_tool(tool_id: int, tool_data: ToolUpdate) -> Optional[Tool]:
        """Update tool"""
        tool = await ToolService.get_tool_by_id(tool_id)
        if not tool:
            return None

        update_data = tool_data.model_dump(exclude_unset=True)
        await tool.update_from_dict(update_data)
        await tool.save()
        return tool

    @staticmethod
    async def delete_tool(tool_id: int) -> bool:
        """Delete tool"""
        tool = await ToolService.get_tool_by_id(tool_id)
        if not tool:
            return False

        await tool.delete()
        return True

    @staticmethod
    async def get_active_tools() -> List[Tool]:
        """Get active tools"""
        tools = await Tool.filter(enabled=True).all()
        return tools

    @staticmethod
    async def get_all_tools() -> List[Tool]:
        """Get all tools"""
        return await Tool.all()
