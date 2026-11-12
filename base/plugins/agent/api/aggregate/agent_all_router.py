"""Agent 插件路由聚合（AC-PLR-01-2：路由只能由 manifest 声明装配）。

此前 ``base/plugins/agent/__init__.py`` 在模块顶层导出 ``router``，并在
``on_enable(app)`` 里自行 ``app.include_router(router)``，既绕过了装配器，
也会与 manifest 声明的 combined_router 互相覆盖、重复注册，且不受统一
请求期门控保护。现改为本文件集中聚合，由 ``manifest.routes`` 指向本目录，
装配器按约定加载后套 ``route_prefix`` 并注入插件启用态依赖。

注意：``api/v1/agent.py`` 与 ``workflow.py`` 各导出两个 APIRouter，装配器每个
文件只取首个匹配的候选变量，故这里显式 include 第二个（execution /
workflow_execution），保持与旧 ``_setup_routes()`` 完全一致的路由集合。
"""
from fastapi import APIRouter

from base.common.response import success_response
from base.plugins.agent.api.v1 import (
    admin_grant_router,
    agent,
    checkpoint,
    dialog_flow,
    joke,
    memory,
    rag,
    skill,
    skill_category,
    tool,
    tool_tag,
    u_execution_router,
    u_resource_router,
    u_workflow_router,
    workflow,
)

router = APIRouter()


@router.get("/test")
async def test_endpoint():
    """测试端点（原 _setup_routes 内联定义，迁移至此保持路径不变）。"""
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
