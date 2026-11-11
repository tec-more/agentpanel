"""Harness Plugin - DeepSeek Harness 业务接入"""
from base.plugins.harness.services.gateway_config import validate_issuance_config


async def on_startup() -> None:
    """启动即校验网关 fail-closed 约束，并显式注入共享域实现。

    - `policy_service.configure_app()`：共享审批策略绑定 manifest 配置读取器（C4）。

    额度计量已统一由网关完成，app 不再注册 `quota_backend` 实现。
    """
    validate_issuance_config()

    from base.plugins.harness.services import policy_service

    policy_service.configure_app()
