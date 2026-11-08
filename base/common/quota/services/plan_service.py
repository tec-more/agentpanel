"""兼容层：套餐服务已迁至 `packages.agentpanel_common.quota.services.plan_service`（P3 D-P3-2=B）。

导入时注入 L2 的 ORM 解析器，保持 L2 解析结果与拆分前逐字段一致。
"""
from base.common.quota.services.plan_resolver import L2PlanResolver
from packages.agentpanel_common.quota.services import plan_service as _shared

_shared.configure(L2PlanResolver())

from packages.agentpanel_common.quota.services.plan_service import *  # noqa: E402,F401,F403
from packages.agentpanel_common.quota.services.plan_service import PlanService  # noqa: E402,F401
