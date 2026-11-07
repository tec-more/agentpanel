"""L2 日志入口：实现已迁至共享包，这里只注入 L2 配置（对外 API 不变）。"""
from base.common.setting import settings
from packages.agentpanel_common import log as _shared_log
from packages.agentpanel_common.log import (  # noqa: F401
    InterceptHandler,
    cleanup_logging,
    json_formatter,
    log,
)


def setup_logging():
    """按 L2 的 config.conf 配置（app_name/debug/日志目录/ELK）初始化日志。"""
    _shared_log.setup_logging(
        app_name=settings.app_name,
        debug=settings.debug,
        log_dir=settings.LOG_DIR,
        elk_enabled=getattr(settings, "ELK_ENABLED", False),
    )
