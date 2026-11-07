"""llm provider 的共享上游传输参数（实际调用由 base.common.upstream 完成）。"""
from base.common.upstream import EgressPolicy, UpstreamConfig

CHAT_READ_TIMEOUT = 60.0
STREAM_READ_TIMEOUT = 120.0


def chat_config() -> UpstreamConfig:
    # trust_env=True：保持 llm 原有的环境变量代理行为
    return UpstreamConfig(read_timeout=CHAT_READ_TIMEOUT, total_timeout=0.0, trust_env=True)


def stream_config() -> UpstreamConfig:
    return UpstreamConfig(read_timeout=STREAM_READ_TIMEOUT, total_timeout=0.0, trust_env=True)


def egress_policy(kind: str, endpoint_url: str = "") -> EgressPolicy:
    """强制出网策略：仅本地 provider 允许回环/私网，其余一律拒绝。"""
    return EgressPolicy.for_provider(kind, endpoint_url)
