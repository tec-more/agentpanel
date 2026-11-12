"""
Agent Development Base Plugin

路由装配约定（AC-PLR-01-2 / AC-PLR-03-1）：
- 本模块**不再导出 router**，也不在 on_enable 里自行 include_router；
- 路由统一由 manifest.routes 声明的 ``api/aggregate`` 目录聚合，
  经装配器套 route_prefix 并注入插件启用态依赖（停用即 404）。
"""
async def on_enable(app):
    """Enable plugin（路由由装配器注册，钩子不再重复挂载）。"""
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
