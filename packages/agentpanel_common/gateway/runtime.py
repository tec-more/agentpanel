"""网关运行时配置访问器（共享实现，P3 T3.7）。

网关模块不直接读取 L2 manifest / `config.conf`；配置源由入口注入：
- L3 新入口：`app/config.py` 的 `gateway_config` / `gateway_upstream_config`
- L2 旧入口（兼容层）：`base/common/gateway/config.py` 的 `configure_shared_runtime()`
"""
from typing import Any, Callable, Dict, Optional

from ..upstream import UpstreamConfig

_config_provider: Optional[Callable[[], Dict[str, Any]]] = None
_upstream_provider: Optional[Callable[[], UpstreamConfig]] = None
_lease_ttl_provider: Optional[Callable[..., int]] = None


def configure(*, config_provider: Optional[Callable[[], Dict[str, Any]]] = None,
              upstream_provider: Optional[Callable[[], UpstreamConfig]] = None,
              lease_ttl_provider: Optional[Callable[..., int]] = None) -> None:
    global _config_provider, _upstream_provider, _lease_ttl_provider
    if config_provider is not None:
        _config_provider = config_provider
    if upstream_provider is not None:
        _upstream_provider = upstream_provider
    if lease_ttl_provider is not None:
        _lease_ttl_provider = lease_ttl_provider


def gateway_config() -> Dict[str, Any]:
    if _config_provider is None:
        return {}
    return _config_provider()


def lease_cache_ttl_seconds(cfg: Optional[Dict[str, Any]] = None) -> int:
    """租约状态缓存 TTL，限定在 5-10 秒。"""
    if _lease_ttl_provider is not None:
        return int(_lease_ttl_provider(cfg))
    raw = (cfg or gateway_config()).get("lease_cache_ttl_seconds") or 8
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 8
    return max(5, min(10, value))


def gateway_upstream_config() -> UpstreamConfig:
    """把网关配置映射成共享上游客户端配置（trust_env/follow_redirects 保持关闭）。"""
    if _upstream_provider is not None:
        return _upstream_provider()
    return build_upstream_config(gateway_config())


def build_upstream_config(cfg: Dict[str, Any]) -> UpstreamConfig:
    raw_statuses = cfg.get("retry_statuses") or []
    if isinstance(raw_statuses, int):
        raw_statuses = [raw_statuses]
    try:
        retry_statuses = tuple(int(x) for x in raw_statuses)
    except (TypeError, ValueError):
        retry_statuses = UpstreamConfig.retry_statuses
    return UpstreamConfig(
        connect_timeout=float(cfg.get("connect_timeout_seconds") or 10),
        read_timeout=float(cfg.get("upstream_timeout_seconds") or 300),
        total_timeout=float(cfg.get("total_timeout_seconds") or 0),
        max_connections=int(cfg.get("max_connections") or 100),
        max_keepalive_connections=int(cfg.get("max_keepalive_connections") or 20),
        keepalive_expiry=float(cfg.get("keepalive_expiry_seconds") or 30),
        verify_tls=bool(cfg.get("verify_tls", True)),
        proxy_url=str(cfg.get("proxy_url") or ""),
        trust_env=bool(cfg.get("trust_env", False)),
        follow_redirects=False,
        http2=False,
        retry_attempts=int(cfg.get("retry_max_attempts") or 1),
        retry_backoff=float(cfg.get("retry_backoff_seconds") or 0.5),
        retry_max_backoff=float(cfg.get("retry_max_backoff_seconds") or 4.0),
        retry_statuses=retry_statuses,
    )
