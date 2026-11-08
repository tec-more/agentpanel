"""兼容层：租约鉴权已迁至 `packages.agentpanel_common.gateway.lease_auth`（P3 T3.3/T3.7）。"""
from base.common.gateway.config import configure_shared_runtime
import base.common.cache  # noqa: F401（触发共享 cache configure）

configure_shared_runtime()

from packages.agentpanel_common.gateway.lease_auth import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.lease_auth import (  # noqa: E402,F401
    authenticate,
    invalidate_lease_cache,
    renew_hint,
)
