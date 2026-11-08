"""兼容层：网关数据面路由已迁至 `packages.agentpanel_common.gateway.router`（P3 T3.2）。"""
from base.common.gateway.config import configure_shared_runtime

configure_shared_runtime()

from packages.agentpanel_common.gateway.router import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.router import gateway_data_router  # noqa: E402,F401
