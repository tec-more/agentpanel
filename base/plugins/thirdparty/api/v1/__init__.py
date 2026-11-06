"""
第三方平台API路由
"""
from fastapi import APIRouter
from .platform import platform_router
from .agent import agent_router

api_router = APIRouter(prefix="/thirdparty")
api_router.include_router(platform_router)
api_router.include_router(agent_router)

__all__ = ["api_router"]