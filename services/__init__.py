"""L3 独立服务集合（网关 / 编排）。

仅作为 Python 包边界存在，使 `services.gateway.common.*` 在
L2 后台与网关服务两种进程中保持同一个导入路径（编排服务已解耦，
不再引用网关领域包，改引 `packages/common/gateway_constants.py`）。
"""
