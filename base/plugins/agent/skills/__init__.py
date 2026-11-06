"""
Skills（技能）模块
技能由后台管理，存储在数据库中
"""
from .base import BaseSkill
from .registry import SkillRegistry, SkillInfo

__all__ = ['BaseSkill', 'SkillRegistry', 'SkillInfo']
