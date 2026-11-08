"""兼容层：网关转发/记账已迁至 `packages.agentpanel_common.gateway.service`（P3 T3.2）。"""
from base.common.gateway.config import configure_shared_runtime
from base.plugins.harness.services.model_credential_service import configure_l2

configure_shared_runtime()
configure_l2()

from packages.agentpanel_common.gateway.service import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.service import (  # noqa: E402,F401
    GatewayProxyError,
    resolve_upstream_credential,
    strip_request_fields,
)
