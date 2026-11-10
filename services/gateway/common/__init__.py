"""网关领域包：数据面路由、租约鉴权、预算/审计与稳定契约。

位于网关服务目录内，由 app（签发租约 / 看板 / embedded 挂载）与网关进程共享；
统一以 `services.gateway.common.*` 绝对导入，避免同包被两种路径重复加载。

命名说明：这里的 `common` 是**网关服务自己的领域包**，不是跨进程共享基础包
`packages/common/`，也不是 app 的 `base/common/` 兼容层；三者互不等价。
2026-11-09 本目录曾名为 `services/gateway/gateway/`，同日改为现名。
编排服务已解耦，不再引用本包：它需要的网关边界常量来自
`packages.common.gateway_constants`。
`constants.py` 仅作为历史导入名的兼容层。
"""
