"""兼容层：网关应用工厂已迁至 `packages.agentpanel_common.gateway.app`（P3 T3.2）。"""
from base.common.gateway.config import configure_shared_runtime

configure_shared_runtime()

from packages.agentpanel_common.gateway.app import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.app import create_gateway_app  # noqa: E402,F401
