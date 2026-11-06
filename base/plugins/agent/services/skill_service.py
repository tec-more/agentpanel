"""
Skill service
"""
import re
from typing import List, Optional
from tortoise.exceptions import DoesNotExist
from base.plugins.agent.models.skill import Skill
from base.plugins.agent.models.skill_category import SkillCategory
from base.plugins.agent.schemas.skill import SkillCreate, SkillUpdate
class SkillService:
    model = "skill"
    """Skill service class"""

    @staticmethod
    def parse_bound_tools(implementation: str) -> List[str]:
        """
        Parse bound tools from skill implementation (Markdown content)

        Extracts tool names from the following format in markdown:
        ## 🔧 可用工具
        - tool_name1
        - tool_name2

        Or:
        ## 可用工具
        - amazon_order_query（订单查询）
        - amazon_fee_query（费用查询）
        """
        if not implementation:
            return []

        tools = []
        lines = implementation.split('\n')
        in_tools_section = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith('##') and ('可用工具' in stripped or '工具列表' in stripped or '可用工具' in stripped):
                in_tools_section = True
                continue

            if in_tools_section:
                if stripped.startswith('##'):
                    in_tools_section = False
                    break

                tool_match = re.match(r'^[-*]\s*(?:\[.*?\]\s*)?([a-zA-Z_][a-zA-Z0-9_]*)', stripped)
                if tool_match:
                    tool_name = tool_match.group(1)
                    if tool_name and tool_name not in tools:
                        tools.append(tool_name)
                elif stripped.startswith('-') or stripped.startswith('*'):
                    continue
                elif stripped and not stripped.startswith('#'):
                    if stripped.startswith('-') or stripped.startswith('*'):
                        parts = stripped[1:].strip().split('（')[0].split('(')[0].strip()
                        if parts and parts not in tools:
                            tools.append(parts)

        return tools

    @staticmethod
    async def create_skill(skill_data: SkillCreate) -> Skill:
        """Create skill"""
        skill = await Skill.create(
            name=skill_data.name,
            description=skill_data.description,
            implementation=skill_data.implementation,
            status=skill_data.status,
            category_id=skill_data.category_id
        )
        
        if skill_data.tool_tag_ids:
            await skill.tool_tags.add(*skill_data.tool_tag_ids)
        
        return skill

    @staticmethod
    async def get_skills(skip: int = 0, limit: int = 100, name: str = "", status: str = "", category_id: int = None) -> List[Skill]:
        """Get skill list"""
        query = Skill.all()
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        if category_id:
            query = query.filter(category_id=category_id)
        skills = await query.offset(skip).limit(limit)
        return skills

    @staticmethod
    async def get_skill_by_id(skill_id: int) -> Optional[Skill]:
        """Get skill by ID"""
        try:
            skill = await Skill.get(id=skill_id)
            return skill
        except DoesNotExist:
            return None

    @staticmethod
    async def update_skill(skill_id: int, skill_data: SkillUpdate) -> Optional[Skill]:
        """Update skill"""
        skill = await SkillService.get_skill_by_id(skill_id)
        if not skill:
            return None

        update_data = skill_data.model_dump(exclude_unset=True)
        tool_tag_ids = update_data.pop('tool_tag_ids', None)
        
        await skill.update_from_dict(update_data)
        await skill.save()
        
        if tool_tag_ids is not None:
            await skill.tool_tags.clear()
            if tool_tag_ids:
                await skill.tool_tags.add(*tool_tag_ids)
        
        return skill

    @staticmethod
    async def delete_skill(skill_id: int) -> bool:
        """Delete skill"""
        skill = await SkillService.get_skill_by_id(skill_id)
        if not skill:
            return False

        await skill.delete()
        return True

    @staticmethod
    async def get_active_skills() -> List[Skill]:
        """Get active skills"""
        skills = await Skill.filter(status="active").all()
        return skills

    @staticmethod
    async def get_skills_by_category(category_id: int) -> List[Skill]:
        """Get skills by category"""
        skills = await Skill.filter(category_id=category_id, status="active").all()
        return skills

    @staticmethod
    async def execute_skill(skill_id: int, parameters: dict) -> dict:
        """Execute skill"""
        skill = await SkillService.get_skill_by_id(skill_id)
        if not skill or skill.status != "active":
            return {"success": False, "message": "Skill not found or inactive"}

        try:
            return {
                "success": True,
                "skill_id": skill_id,
                "skill_name": skill.name,
                "content_preview": skill.implementation[:200] + "..." if skill.implementation else None,
                "message": "Skill content loaded successfully"
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    async def get_skill_usage(skill_id: int) -> dict:
        """Get skill usage information"""
        skill = await SkillService.get_skill_by_id(skill_id)
        if not skill:
            return {"error": "Skill not found"}

        try:
            agents = await skill.agents.all()
            agent_count = len(agents)
            agent_names = [agent.name for agent in agents]
        except Exception:
            agent_count = 0
            agent_names = []

        return {
            "skill_id": skill_id,
            "skill_name": skill.name,
            "agent_count": agent_count,
            "agents": agent_names
        }

    @staticmethod
    async def get_skill_content(skill_id: int) -> Optional[dict]:
        """Get skill content (Markdown)"""
        skill = await SkillService.get_skill_by_id(skill_id)
        if not skill:
            return None

        return {
            "id": skill.id,
            "name": skill.name,
            "content": skill.implementation or ""
        }

    @staticmethod
    async def get_skill_with_category(skill_id: int) -> Optional[dict]:
        """Get skill with category information"""
        skill = await SkillService.get_skill_by_id(skill_id)
        if not skill:
            return None

        category_name = None
        if skill.category_id:
            category = await SkillCategory.get_or_none(id=skill.category_id)
            if category:
                category_name = category.name

        try:
            agent_count = await skill.agents.count()
        except Exception:
            agent_count = 0

        bound_tools = []
        tool_tag_ids = []
        try:
            tool_tags = await skill.tool_tags.all()
            tool_tag_ids = [tag.id for tag in tool_tags]
            for tag in tool_tags:
                try:
                    tools = await tag.tools.all()
                    for tool in tools:
                        if tool.name not in bound_tools:
                            bound_tools.append(tool.name)
                except Exception:
                    continue
        except Exception:
            pass

        return {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "implementation": skill.implementation,
            "status": skill.status,
            "category_id": skill.category_id,
            "category_name": category_name,
            "created_at": skill.created_at,
            "updated_at": skill.updated_at,
            "agent_count": agent_count,
            "bound_tools": bound_tools,
            "tool_tag_ids": tool_tag_ids
        }

    @staticmethod
    async def get_all_skills_with_category() -> List[dict]:
        """Get all skills with category information"""
        skills = await Skill.all()
        result = []

        for skill in skills:
            detail = await SkillService.get_skill_with_category(skill.id)
            if detail:
                result.append(detail)

        return result
