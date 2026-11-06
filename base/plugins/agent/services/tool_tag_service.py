"""
Tool Tag service
"""
from typing import List, Optional
from tortoise.exceptions import DoesNotExist, IntegrityError
from base.plugins.agent.models.tool_tag import ToolTag
from base.plugins.agent.models.tool import Tool
from base.plugins.agent.schemas.tool_tag import ToolTagCreate, ToolTagUpdate
class ToolTagService:
    model = "tool_tag"
    """Tool tag service class"""

    @staticmethod
    async def create_tag(tag_data: ToolTagCreate) -> Optional[ToolTag]:
        """Create tag"""
        try:
            tag = await ToolTag.create(
                name=tag_data.name,
                description=tag_data.description,
                color=tag_data.color,
                sort_order=tag_data.sort_order,
                enabled=tag_data.enabled
            )
            return tag
        except IntegrityError:
            return None

    @staticmethod
    async def get_tags(skip: int = 0, limit: int = 100, name: str = "", enabled: bool = None) -> List[ToolTag]:
        """Get tag list"""
        query = ToolTag.all()
        if name:
            query = query.filter(name__icontains=name)
        if enabled is not None:
            query = query.filter(enabled=enabled)
        tags = await query.offset(skip).limit(limit)
        return tags

    @staticmethod
    async def get_tag_by_id(tag_id: int) -> Optional[ToolTag]:
        """Get tag by ID"""
        try:
            tag = await ToolTag.get(id=tag_id)
            return tag
        except DoesNotExist:
            return None

    @staticmethod
    async def get_tag_by_name(name: str) -> Optional[ToolTag]:
        """Get tag by name"""
        try:
            tag = await ToolTag.get(name=name)
            return tag
        except DoesNotExist:
            return None

    @staticmethod
    async def update_tag(tag_id: int, tag_data: ToolTagUpdate) -> Optional[ToolTag]:
        """Update tag"""
        tag = await ToolTagService.get_tag_by_id(tag_id)
        if not tag:
            return None

        update_data = tag_data.model_dump(exclude_unset=True)
        await tag.update_from_dict(update_data)
        await tag.save()
        return tag

    @staticmethod
    async def delete_tag(tag_id: int) -> bool:
        """Delete tag"""
        tag = await ToolTagService.get_tag_by_id(tag_id)
        if not tag:
            return False

        await tag.delete()
        return True

    @staticmethod
    async def get_active_tags() -> List[ToolTag]:
        """Get active tags"""
        tags = await ToolTag.filter(enabled=True).all()
        return tags

    @staticmethod
    async def get_tags_with_count() -> List[dict]:
        """Get tags with tool count"""
        tags = await ToolTag.all()
        result = []
        for tag in tags:
            try:
                count = await tag.tools.all().count()
            except Exception:
                count = 0
            result.append({
                "id": tag.id,
                "name": tag.name,
                "description": tag.description,
                "color": tag.color,
                "sort_order": tag.sort_order,
                "enabled": tag.enabled,
                "created_at": tag.created_at,
                "updated_at": tag.updated_at,
                "tool_count": count
            })
        return result

    @staticmethod
    async def get_all_tags() -> List[ToolTag]:
        """Get all tags"""
        return await ToolTag.all()
