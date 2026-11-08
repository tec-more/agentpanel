"""兼容层：网关审计已迁至 `packages.agentpanel_common.gateway.audit`（P3 T3.2）。"""
from base.common.gateway.config import configure_shared_runtime

configure_shared_runtime()

from packages.agentpanel_common.gateway.audit import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.audit import (  # noqa: E402,F401
    record_gateway_auth_reject,
    record_gateway_quota_event,
)
