"""网关领域包：数据面路由、租约鉴权、预算/审计与稳定契约。

位于网关服务目录内，由 L2（签发租约 / 看板 / embedded 挂载）与网关进程共享；
统一以 `services.gateway.gateway.*` 绝对导入，避免同包被两种路径重复加载。
编排服务已解耦，不再引用本包：它需要的网关边界常量来自
`packages.agentpanel_common.gateway_constants`。
`constants.py` 仅作为历史导入名的兼容层。
"""
