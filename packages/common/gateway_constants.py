"""网关边界契约（跨进程共享，轻量无依赖）。

这里只放 L2、L3 网关、L3 编排三方都要判定的**纯常量与纯函数**：
数据面挂载前缀、租约虚拟 key 格式、日志分流标记、审计来源。

放在共享基础包而非网关服务目录，是为了保持依赖方向单向：
``packages.common`` 不 import ``services.*`` / ``base.*``，
三个进程都从同一模块身份读取，避免常量定义漂移或重复加载。
网关服务目录内的 ``services.gateway.common.constants`` 保留为兼容层。
"""

# 数据面统一前缀；与业务 API（/v1/llm、/v1/harness 等）结构隔离
GATEWAY_DEPLOY_PREFIX = "/v1/gateway"

# 租约虚拟 key 格式：dgw.<lease_id>.<secret>
GATEWAY_VIRTUAL_KEY_PREFIX = "dgw"

# loguru extra 标记：网关日志写入独立 sink（logs/gateway.log）
GATEWAY_LOG_COMPONENT = "gateway"

# 网关审计事件来源（HarnessAuditEvent.event_source）
GATEWAY_EVENT_SOURCE = "gateway"


def is_gateway_virtual_key(token: str) -> bool:
    """是否为网关租约虚拟 key（仅做格式判断，不做鉴权）。"""
    return bool(token) and str(token).strip().startswith(f"{GATEWAY_VIRTUAL_KEY_PREFIX}.")


def looks_like_jwt(token: str) -> bool:
    """粗略识别 JWT（三段式且首段为 base64url 的 eyJ 前缀）。"""
    parts = str(token or "").strip().split(".")
    return len(parts) == 3 and parts[0].startswith("eyJ")


__all__ = [
    "GATEWAY_DEPLOY_PREFIX",
    "GATEWAY_VIRTUAL_KEY_PREFIX",
    "GATEWAY_LOG_COMPONENT",
    "GATEWAY_EVENT_SOURCE",
    "is_gateway_virtual_key",
    "looks_like_jwt",
]
