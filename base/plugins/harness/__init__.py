"""Harness Plugin - DeepSeek Harness 业务接入"""
from base.common.gateway.config import validate_issuance_config


async def on_startup() -> None:
    """启动即校验网关 fail-closed 约束；不合规直接拒绝启动。"""
    validate_issuance_config()

