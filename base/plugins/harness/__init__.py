"""Harness Plugin - DeepSeek Harness 业务接入"""
from base.plugins.harness.services.gateway_config import validate_issuance_config


async def on_startup() -> None:
    """启动即校验网关 fail-closed 约束，并显式注入共享域实现。

    - `quota_backend.configure_app()`：共享额度分派器绑定 app 直调 QuotaService 的实现；
    - `policy_service.configure_app()`：共享审批策略绑定 manifest 配置读取器（C4）。
    """
    validate_issuance_config()

    from base.plugins.harness.services import policy_service, quota_backend

    quota_backend.configure_app()
    policy_service.configure_app()
