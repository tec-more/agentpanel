"""兼容层：网关边界常量唯一来源已下沉到共享基础包。

历史上本模块位于 L2 的 ``base/common/gateway/constants.py``，P1 迁入共享包、
P7 目录整理又随网关领域包迁入服务目录，导致 ``packages.agentpanel_common.log``
反向依赖 ``services.*``、编排镜像必须复制整个网关包。现已把定义下沉到
``packages.agentpanel_common.gateway_constants``，本模块仅做 re-export，
保留 ``services.gateway.gateway.constants`` 导入名以免破坏外部/历史引用。

新代码请直接 import ``packages.agentpanel_common.gateway_constants``。
"""
from packages.agentpanel_common.gateway_constants import (  # noqa: F401
    GATEWAY_DEPLOY_PREFIX,
    GATEWAY_EVENT_SOURCE,
    GATEWAY_LOG_COMPONENT,
    GATEWAY_VIRTUAL_KEY_PREFIX,
    is_gateway_virtual_key,
    looks_like_jwt,
)

__all__ = [
    "GATEWAY_DEPLOY_PREFIX",
    "GATEWAY_VIRTUAL_KEY_PREFIX",
    "GATEWAY_LOG_COMPONENT",
    "GATEWAY_EVENT_SOURCE",
    "is_gateway_virtual_key",
    "looks_like_jwt",
]
