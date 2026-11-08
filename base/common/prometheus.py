"""兼容层：实现已迁至共享包 `packages.agentpanel_common.prometheus`（P3 T3.6）。

L2 继续使用同一 CollectorRegistry；这里注入 settings 作为配置源。
"""
from base.common.setting import settings
from packages.agentpanel_common import prometheus as _shared
from packages.agentpanel_common.prometheus import *  # noqa: F401,F403

_shared.configure_settings(lambda: settings)
