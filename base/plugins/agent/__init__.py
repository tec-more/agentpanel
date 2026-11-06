"""
Agent Development Base Plugin
"""

from fastapi import APIRouter

router = APIRouter(prefix="/v1/agent")


def _setup_routes():
    """延迟设置路由，避免提前导入模型"""
    from .api.v1 import dialog_flow, workflow, agent, skill, skill_category, tool, tool_tag, memory, joke, rag, checkpoint
    from .api.v1 import u_workflow_router, u_execution_router, u_resource_router, admin_grant_router
    
    @router.get("/test")
    async def test_endpoint():
        """测试端点"""
        print("=== 测试端点被调用 ===")
        from base.common.response import success_response
        return success_response(data={"message": "测试成功"}, msg="测试端点响应成功")

    router.include_router(agent.agent_router)
    router.include_router(agent.execution_router)
    router.include_router(skill.skill_router)
    router.include_router(skill_category.skill_category_router)
    router.include_router(tool.tool_router)
    router.include_router(tool_tag.tool_tag_router)
    router.include_router(memory.memory_router)
    router.include_router(u_workflow_router.router)
    router.include_router(u_execution_router.router)
    router.include_router(u_resource_router.router)   # T11 用户侧资源授权清单
    router.include_router(admin_grant_router.router)  # T11 管理侧授权管理
    router.include_router(workflow.workflow_router)
    router.include_router(workflow.workflow_execution_router)
    router.include_router(dialog_flow.dialog_flow_router)
    router.include_router(joke.joke_router)
    router.include_router(rag.rag_router)
    router.include_router(checkpoint.router)


async def on_enable(app):
    """Enable plugin"""
    _setup_routes()
    app.include_router(router)
    return True

async def on_disable():
    """Disable plugin"""
    return True

async def on_startup():
    """Startup hook"""
    # 延迟导入技能模块，避免循环导入
    try:
        from base.plugins.agent.skills.registry import SkillRegistry
        await SkillRegistry.auto_register_all()
    except Exception as e:
        print(f"Error registering skills: {e}")
    # T6/M2 断点标记（F5：进程重启后运行中实例标记 interrupted，P0 不自动恢复）
    try:
        from base.plugins.agent.services.execution_service import ExecutionService
        await ExecutionService.mark_interrupted_on_startup()
    except Exception as e:
        print(f"Error marking interrupted executions: {e}")

async def on_shutdown():
    """Shutdown hook"""
    # T6/M2：退出前兜底 flush Trace 缓冲（R-11）
    try:
        from base.plugins.agent.services.trace_service import TraceService
        await TraceService.close_all()
    except Exception as e:
        print(f"Error flushing trace writers: {e}")