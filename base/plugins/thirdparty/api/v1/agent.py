"""
第三方平台智能体API接口
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from base.common.response import SuccessResponse
from base.common.security import get_current_user_id
from base.plugins.thirdparty.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from base.plugins.thirdparty.services.agent_service import AgentService

agent_router = APIRouter(prefix="/agents", tags=["第三方平台智能体"])


@agent_router.post("/", response_model=AgentResponse)
async def create_agent(
    agent_data: AgentCreate,
    current_user_id: int = Depends(get_current_user_id)
):
    """创建第三方平台智能体"""
    agent = await AgentService.create_agent(agent_data)
    return SuccessResponse(data=agent)


@agent_router.get("/", response_model=List[AgentResponse])
async def get_agents(
    skip: int = 0,
    limit: int = 100,
    current_user_id: int = Depends(get_current_user_id)
):
    """获取第三方平台智能体列表"""
    agents = await AgentService.get_agents(skip, limit)
    return SuccessResponse(data=agents)


@agent_router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """获取第三方平台智能体详情"""
    agent = await AgentService.get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return SuccessResponse(data=agent)


@agent_router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    current_user_id: int = Depends(get_current_user_id)
):
    """更新第三方平台智能体"""
    agent = await AgentService.update_agent(agent_id, agent_data)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return SuccessResponse(data=agent)


@agent_router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """删除第三方平台智能体"""
    success = await AgentService.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return SuccessResponse(msg="智能体删除成功")


@agent_router.get("/platform/{platform_id}", response_model=List[AgentResponse])
async def get_agents_by_platform(
    platform_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """根据平台ID获取智能体列表"""
    agents = await AgentService.get_agents_by_platform(platform_id)
    return SuccessResponse(data=agents)


@agent_router.post("/{agent_id}/test")
async def test_agent_access(
    agent_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """测试智能体访问"""
    success = await AgentService.test_agent_access(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return SuccessResponse(data={"accessible": success}, msg="访问测试成功")