"""网关边界常量（轻量模块，避免业务鉴权模块引入插件依赖）"""

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
