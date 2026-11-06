"""
Skill（技能）基类
技能由后台管理，存储在数据库中
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseSkill:
    """
    技能基类
    技能的内容（markdown）存储在数据库的 implementation 字段中
    """
    
    @classmethod
    def get_name(cls) -> str:
        """获取技能名称"""
        return cls.__name__
    
    @classmethod
    def get_description(cls) -> str:
        """获取技能描述"""
        return cls.__doc__ or ""
    
    @classmethod
    def get_required_tools(cls) -> list:
        """
        获取技能依赖的工具列表
        子类可重写
        """
        return []
