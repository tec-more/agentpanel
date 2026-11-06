"""
Audit Plugin API v1 路由
"""

from base.plugins.audit.api.v1.login_log import login_log_router
from base.plugins.audit.api.v1.audit_log import audit_log_router
from base.plugins.audit.api.v1.data_change_log import data_change_log_router
from base.plugins.audit.api.v1.audit_config import audit_config_router
from base.plugins.audit.api.v1.trace import trace_router
from base.plugins.audit.api.v1.risks import risks_router
from base.plugins.audit.api.v1.reports import reports_router

__all__ = [
    "login_log_router",
    "audit_log_router", 
    "data_change_log_router",
    "audit_config_router",
    "trace_router",
    "risks_router",
    "reports_router"
]