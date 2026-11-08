"""兼容层：网关日志已迁至 `packages.agentpanel_common.gateway.logging`（P3 T3.2）。"""
from base.common.gateway.config import configure_shared_runtime

configure_shared_runtime()

from packages.agentpanel_common.gateway.logging import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.logging import gateway_logger  # noqa: E402,F401
