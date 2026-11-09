"""兼容层：实现已迁至共享包 `packages.common.prometheus`（P3 T3.6）。

L2 继续使用同一 CollectorRegistry；这里注入 settings 作为配置源。
"""
from base.common.setting import settings
from packages.common import prometheus as _shared
from packages.common.prometheus import *  # noqa: F401,F403

_shared.configure_settings(lambda: settings)
