"""兼容层：网关数据面鉴权已迁至 `packages.agentpanel_common.gateway.auth`（P3 T3.2）。"""
from base.common.gateway.config import configure_shared_runtime

configure_shared_runtime()

from packages.agentpanel_common.gateway.auth import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.auth import require_gateway_lease  # noqa: E402,F401
