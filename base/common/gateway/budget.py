"""兼容层：网关预算/并发已迁至 `packages.agentpanel_common.gateway.budget`（P3 T3.3）。"""
from base.common.gateway.config import configure_shared_runtime
import base.common.cache  # noqa: F401（触发共享 cache configure）
import base.common.quota.services.plan_service  # noqa: F401（注入 L2 ORM 套餐解析器）

configure_shared_runtime()

from packages.agentpanel_common.gateway.budget import *  # noqa: E402,F401,F403
from packages.agentpanel_common.gateway.budget import (  # noqa: E402,F401
    GatewayBudgetService,
    GatewayQuotaError,
    apply_request_caps,
    estimate_completion_tokens,
)
