"""兼容层：配额核心服务已迁至 `packages.common.quota.services.quota_service`（P3 D-P3-2=B）。

app 既有 import 路径不变；先导入 `base.common.cache` 确保共享缓存已注入 settings。
"""
from base.common.cache import RedisCache  # noqa: F401（触发共享 cache configure）
from packages.common.quota.services.quota_service import *  # noqa: F401,F403
from packages.common.quota.services.quota_service import QuotaService  # noqa: F401
