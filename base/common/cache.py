"""兼容层：Redis 缓存实现已迁至 `packages.agentpanel_common.cache`（P3 T3.6）。

L2 既有 import 路径保持不变；导入时用 settings 注入连接参数。
"""
from base.common.setting import settings
from packages.agentpanel_common.cache import configure as _configure
from packages.agentpanel_common.cache import *  # noqa: F401,F403
from packages.agentpanel_common.cache import RedisCache, get_cache  # noqa: F401

_configure(
    enabled=bool(getattr(settings, "REDIS_ENABLED", False)),
    host=getattr(settings, "REDIS_HOST", "127.0.0.1"),
    port=int(getattr(settings, "REDIS_PORT", 6379)),
    password=getattr(settings, "REDIS_PASSWORD", None) or None,
    db=int(getattr(settings, "REDIS_DB", 0)),
)
