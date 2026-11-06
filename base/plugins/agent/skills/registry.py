"""
Skill（技能）注册表
技能由后台管理，存储在数据库中
"""
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class SkillInfo:
    """技能信息对象"""
    def __init__(self, skill_id: str, name: str, description: str = "", content: str = ""):
        self.skill_id = skill_id
        self.name = name
        self.description = description
        self.content = content
    
    def get_required_tools(self) -> list:
        """从内容中提取工具（如果需要）"""
        return []
    
    def to_dict(self) -> Dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "content": self.content
        }
    
    @staticmethod
    def execute(params: dict) -> dict:
        """
        执行技能 - 占位方法
        实际执行会在其他地方处理
        """
        input_text = params.get("input_text", "")
        return {
            "success": True,
            "result": f"Processed: {input_text}",
            "message": f"Skill executed successfully"
        }


class SkillRegistry:
    """技能注册表"""
    _skills: Dict[str, SkillInfo] = {}
    
    @classmethod
    def register(cls, skill_id: str, name: str, description: str = "", content: str = "") -> None:
        """
        注册技能
        
        Args:
            skill_id: 技能 ID
            name: 技能名称
            description: 技能描述
            content: 技能内容（markdown 文档）
        """
        skill_info = SkillInfo(skill_id, name, description, content)
        cls._skills[skill_id] = skill_info
        logger.info(f"Registered skill: {skill_id}")
    
    @classmethod
    def get_skill(cls, skill_id: str) -> Optional[SkillInfo]:
        """
        获取技能
        
        Args:
            skill_id: 技能 ID
            
        Returns:
            技能信息
        """
        return cls._skills.get(skill_id)
    
    @classmethod
    def get_all_skills(cls) -> Dict[str, SkillInfo]:
        """
        获取所有注册的技能
        
        Returns:
            技能字典
        """
        return cls._skills
    
    @classmethod
    def get_skill_types(cls) -> list:
        """
        获取所有技能类型（技能 ID 列表）
        
        Returns:
            技能类型列表
        """
        return list(cls._skills.keys())
    
    @classmethod
    def list_skills(cls) -> List[Dict]:
        """
        列出所有技能的信息
        
        Returns:
            技能信息列表
        """
        return [
            skill.to_dict()
            for skill in cls._skills.values()
        ]
    
    @classmethod
    async def load_from_database(cls) -> None:
        """
        从数据库加载所有技能
        """
        try:
            from base.plugins.agent.models.skill import Skill
            
            skills = await Skill.filter(status="active").all()
            
            cls._skills.clear()
            for skill in skills:
                # Use skill.id as skill_id, or convert name to a valid identifier
                skill_id = str(skill.id)
                cls.register(
                    skill_id=skill_id,
                    name=skill.name,
                    description=skill.description or "",
                    content=skill.implementation or ""
                )
            
            logger.info(f"Loaded {len(skills)} skills from database")
        except Exception as e:
            logger.error(f"Failed to load skills from database: {e}")
    
    @classmethod
    async def auto_register_all(cls) -> None:
        """
        自动注册所有技能
        从数据库加载
        """
        await cls.load_from_database()
    
    @classmethod
    def clear(cls) -> None:
        """清空所有注册的技能"""
        cls._skills.clear()
        logger.info("Cleared all skills from registry")
