"""兼容层：网关边界常量唯一来源已下沉到共享基础包。

历史上本模块位于 app 的 ``base/common/gateway/constants.py``，P1 迁入共享包、
P7 目录整理又随网关领域包迁入服务目录（先 ``services/gateway/gateway/``，
同日改名为 ``services/gateway/common/``），导致 ``packages.common.log``
反向依赖 ``services.*``、编排镜像必须复制整个网关包。现已把定义下沉到
``packages.common.gateway_constants``，本模块仅做 re-export，
为包内与外部调用保留 ``services.gateway.common.constants`` 这一稳定入口。

新代码请直接 import ``packages.common.gateway_constants``。
"""
from packages.common.gateway_constants import (  # noqa: F401
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
