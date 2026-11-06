"""
第三方平台智能体服务
"""
from typing import List, Optional
from tortoise.exceptions import DoesNotExist
from base.plugins.thirdparty.models.agent import ThirdPartyAgent
from base.plugins.thirdparty.schemas.agent import AgentCreate, AgentUpdate
class AgentService:
    model = "agent"
    """智能体服务类"""

    @staticmethod
    async def create_agent(agent_data: AgentCreate) -> ThirdPartyAgent:
        """创建智能体"""
        agent = await ThirdPartyAgent.create(
            name=agent_data.name,
            platform_id=agent_data.platform_id,
            agent_id=agent_data.agent_id,
            access_url=agent_data.access_url,
            status=agent_data.status,
            description=agent_data.description,
            config=agent_data.config
        )
        return agent

    @staticmethod
    async def get_agents(skip: int = 0, limit: int = 100) -> List[ThirdPartyAgent]:
        """获取智能体列表"""
        agents = await ThirdPartyAgent.all().offset(skip).limit(limit).prefetch_related('platform')
        return agents

    @staticmethod
    async def get_agent_by_id(agent_id: int) -> Optional[ThirdPartyAgent]:
        """根据ID获取智能体"""
        try:
            agent = await ThirdPartyAgent.get(id=agent_id).prefetch_related('platform')
            return agent
        except DoesNotExist:
            return None

    @staticmethod
    async def update_agent(agent_id: int, agent_data: AgentUpdate) -> Optional[ThirdPartyAgent]:
        """更新智能体"""
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            return None

        update_data = agent_data.model_dump(exclude_unset=True)
        await agent.update_from_dict(update_data)
        await agent.save()
        return agent

    @staticmethod
    async def delete_agent(agent_id: int) -> bool:
        """删除智能体"""
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            return False

        await agent.delete()
        return True

    @staticmethod
    async def get_agents_by_platform(platform_id: int) -> List[ThirdPartyAgent]:
        """根据平台ID获取智能体列表"""
        agents = await ThirdPartyAgent.filter(platform_id=platform_id).prefetch_related('platform')
        return agents

    @staticmethod
    async def test_agent_access(agent_id: int) -> bool:
        """测试智能体访问"""
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            return False

        # TODO: 实现智能体访问测试逻辑
        # 这里需要根据不同平台类型实现不同的访问测试
        # 例如：Dify可以调用其智能体的测试接口
        # Coze可以调用其智能体的预览接口
        return True