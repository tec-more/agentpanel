"""
M8 权限与归属公共模块（base/common 非插件，模型经 get_model_list 显式注册）

分层职责（溯源 docs/arch/05-可靠性与安全可观测.md §2.1 防越权四层）：
- L1 接入层：middleware.owner_context 解析 JWT(typ/sub 同源, R-04) 注入 owner 上下文
- L2 路由层：filter.owned_queryset / get_owned_or_404 声明式归属过滤（R-01，越权 404）
- L3 服务层：guard 复核钩子（写操作/敏感读二次校验，T5/T6 消费）
- 资源授权：service.ResourceGrantService（check_resource_access 等内部接口，04-§6）
- 数据范围：scope.resolve_scope(owner) -> {data_scope, org_ids}（04-§6）
- 越权处置：audit 越权审计(warn) + 高频限流(alert)（F8）
"""
from .constants import OwnerType, DataScope, ResourceType
from .context import (
    OwnerContext,
    get_current_owner,
    require_owner,
    current_owner,
)
from .scope import resolve_scope
from .service import ResourceGrantService, check_resource_access
from .filter import (
    build_owner_filter,
    owned_queryset,
    get_owned_or_404,
    OwnedResourceNotFound,
)
from .guard import assert_owner_access, recheck_owner

__all__ = [
    "OwnerType",
    "DataScope",
    "ResourceType",
    "OwnerContext",
    "get_current_owner",
    "require_owner",
    "current_owner",
    "resolve_scope",
    "ResourceGrantService",
    "check_resource_access",
    "build_owner_filter",
    "owned_queryset",
    "get_owned_or_404",
    "OwnedResourceNotFound",
    "assert_owner_access",
    "recheck_owner",
]
