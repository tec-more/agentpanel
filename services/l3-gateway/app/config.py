"""L3 网关数据面配置契约（仅 manifest 默认值 + `GW_*` 环境变量）。

与 `base/common/gateway/config.py` 的数据面部分逐项一致：
- 默认值来自 `services/l3-gateway/manifest.json` 的 `config.gateway`；
- 覆盖来源为 `GW_*` 环境变量（Spec §5.4）；
- fail-closed 语义不变：`enabled` 时 `fail_closed` 必须为 true、`public_base_url`
  必须 http(s)、provider 白名单非空、TTL/重试/连接池配置合法。

与 L2 的差异：
- 不读 `plugin_manager`，也不读 `config.conf`；
- 不含 `issuance_config()` / `runtime_config()` / `reconciliation_config()`
  （这些只属于 L2 的租约签发与对账）。
"""
from typing import Any, Dict, List

from packages.agentpanel_common.config import (
    REPO_ROOT,
    ConfigError,
    EnvOverride,
    apply_env_overrides,
    load_manifest,
    manifest_section,
    read_env_value,
)
from packages.agentpanel_common.upstream import UpstreamConfig

GATEWAY_MANIFEST = REPO_ROOT / "services" / "l3-gateway" / "manifest.json"

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "deployment": "standalone",
    "port": 9999,
    "host": "127.0.0.1",
    "public_base_url": "",
    "lease_ttl_seconds": 900,
    "renew_ttl_seconds": 900,
    "max_lease_ttl_seconds": 3600,
    # 租户级 TTL 覆盖：{"<owner_type>:<owner_id>": <seconds>}，优先级高于全局默认
    "tenant_lease_ttl_seconds": {},
    # 租约鉴权状态 Redis 短缓存（秒），限定 5-10
    "lease_cache_ttl_seconds": 8,
    "max_rpm": 60,
    "fail_closed": True,
    "provider_domain_allowlist": ["api.deepseek.com"],
    "allow_loopback": False,
    "strip_request_fields": ["dsh_session_log"],
    "upstream_timeout_seconds": 300,
    "connect_timeout_seconds": 10,
    "total_timeout_seconds": 0,
    "health_check_timeout_seconds": 3,
    # ---- 共享上游客户端的重试 / 连接池 / TLS / 代理（默认值不改变既有行为）----
    "retry_max_attempts": 3,
    "retry_backoff_seconds": 0.5,
    "retry_max_backoff_seconds": 4.0,
    "retry_statuses": [429, 500, 502, 503, 504],
    "verify_tls": True,
    "proxy_url": "",
    "trust_env": False,
    "max_connections": 100,
    "max_keepalive_connections": 20,
    "keepalive_expiry_seconds": 30,
    # ---- 额度耗尽中断（共享存储；0 表示不限）----
    "lease_budget_tokens": 0,
    "max_output_tokens_per_request": 4096,
    "max_concurrent_requests_per_owner": 8,
    "estimate_chars_per_token": 2.0,
    "min_output_allowance_tokens": 1,
    "auto_revoke_on_exhausted": True,
    "gateway_quota_ttl_seconds": 86400,
}

# 数据面环境变量覆盖（Spec §5.4）
_GATEWAY_ENV_OVERRIDES: tuple[EnvOverride, ...] = (
    EnvOverride("enabled", "GW_ENABLED", "bool"),
    EnvOverride("deployment", "GW_DEPLOYMENT", "str"),
    EnvOverride("host", "GW_HOST", "str"),
    EnvOverride("port", "GW_PORT", "int"),
    EnvOverride("public_base_url", "GW_PUBLIC_BASE_URL", "str"),
    EnvOverride("fail_closed", "GW_FAIL_CLOSED", "bool"),
    EnvOverride("provider_domain_allowlist", "GW_PROVIDER_DOMAIN_ALLOWLIST", "list"),
    EnvOverride("allow_loopback", "GW_ALLOW_LOOPBACK", "bool"),
    EnvOverride("strip_request_fields", "GW_STRIP_REQUEST_FIELDS", "list"),
    EnvOverride("lease_cache_ttl_seconds", "GW_LEASE_CACHE_TTL_SECONDS", "int"),
    EnvOverride("lease_ttl_seconds", "GW_LEASE_TTL_SECONDS", "int"),
    EnvOverride("renew_ttl_seconds", "GW_RENEW_TTL_SECONDS", "int"),
    EnvOverride("max_lease_ttl_seconds", "GW_MAX_LEASE_TTL_SECONDS", "int"),
    EnvOverride("tenant_lease_ttl_seconds", "GW_TENANT_LEASE_TTL_JSON", "json"),
    EnvOverride("max_rpm", "GW_MAX_RPM", "int"),
    EnvOverride("upstream_timeout_seconds", "GW_UPSTREAM_TIMEOUT_SECONDS", "int"),
    EnvOverride("connect_timeout_seconds", "GW_CONNECT_TIMEOUT_SECONDS", "int"),
    EnvOverride("total_timeout_seconds", "GW_TOTAL_TIMEOUT_SECONDS", "float"),
    EnvOverride("health_check_timeout_seconds", "GW_HEALTH_CHECK_TIMEOUT_SECONDS", "int"),
    EnvOverride("retry_max_attempts", "GW_RETRY_MAX_ATTEMPTS", "int"),
    EnvOverride("retry_backoff_seconds", "GW_RETRY_BACKOFF_SECONDS", "float"),
    EnvOverride("retry_max_backoff_seconds", "GW_RETRY_MAX_BACKOFF_SECONDS", "float"),
    EnvOverride("retry_statuses", "GW_RETRY_STATUSES", "int_list"),
    EnvOverride("verify_tls", "GW_VERIFY_TLS", "bool"),
    EnvOverride("proxy_url", "GW_PROXY_URL", "str"),
    EnvOverride("trust_env", "GW_TRUST_ENV", "bool"),
    EnvOverride("max_connections", "GW_MAX_CONNECTIONS", "int"),
    EnvOverride("max_keepalive_connections", "GW_MAX_KEEPALIVE_CONNECTIONS", "int"),
    EnvOverride("keepalive_expiry_seconds", "GW_KEEPALIVE_EXPIRY_SECONDS", "float"),
    EnvOverride("lease_budget_tokens", "GW_LEASE_BUDGET_TOKENS", "int"),
    EnvOverride("max_output_tokens_per_request", "GW_MAX_OUTPUT_TOKENS_PER_REQUEST", "int"),
    EnvOverride("max_concurrent_requests_per_owner", "GW_MAX_CONCURRENT_REQUESTS_PER_OWNER", "int"),
    EnvOverride("estimate_chars_per_token", "GW_ESTIMATE_CHARS_PER_TOKEN", "float"),
    EnvOverride("min_output_allowance_tokens", "GW_MIN_OUTPUT_ALLOWANCE_TOKENS", "int"),
    EnvOverride("auto_revoke_on_exhausted", "GW_AUTO_REVOKE_ON_EXHAUSTED", "bool"),
    EnvOverride("gateway_quota_ttl_seconds", "GW_GATEWAY_QUOTA_TTL_SECONDS", "int"),
)


class GatewayConfigError(RuntimeError):
    """网关配置不满足 fail-closed 约束"""


def gateway_config() -> Dict[str, Any]:
    """数据面配置：独立 manifest 默认值 + `GW_*` 环境变量覆盖。"""
    manifest = load_manifest(GATEWAY_MANIFEST)
    raw = manifest_section(manifest, "gateway")
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
    try:
        cfg = apply_env_overrides(cfg, _GATEWAY_ENV_OVERRIDES, source="gateway")
    except ConfigError as exc:
        raise GatewayConfigError(str(exc)) from exc
    return cfg


def lease_cache_ttl_seconds(cfg: Dict[str, Any]) -> int:
    """租约状态缓存 TTL，限定在 5-10 秒。"""
    try:
        value = int(cfg.get("lease_cache_ttl_seconds") or 8)
    except (TypeError, ValueError):
        value = 8
    return max(5, min(10, value))


def gateway_upstream_config() -> UpstreamConfig:
    """把网关配置映射成共享上游客户端配置（trust_env/follow_redirects 保持关闭）。"""
    cfg = gateway_config()
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


def upstream_allowlist(cfg: Dict[str, Any]) -> List[str]:
    allow = cfg.get("provider_domain_allowlist") or []
    if isinstance(allow, str):
        allow = [allow]
    return [str(x).strip().lower() for x in allow if str(x).strip()]


def _validate_fail_closed(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not cfg.get("enabled"):
        return cfg
    if not cfg.get("fail_closed"):
        raise GatewayConfigError("网关模式下 gateway.fail_closed 必须为 true")
    if str(cfg.get("deployment")) not in ("standalone", "embedded"):
        raise GatewayConfigError("gateway.deployment 仅支持 standalone/embedded")
    base_url = str(cfg.get("public_base_url") or "").strip()
    if not base_url.startswith(("http://", "https://")):
        raise GatewayConfigError("gateway.public_base_url 必须显式配置为 http(s) 地址")
    if not upstream_allowlist(cfg):
        raise GatewayConfigError("gateway.provider_domain_allowlist 不能为空（出网白名单）")
    ttl = int(cfg.get("lease_ttl_seconds") or 0)
    max_ttl = int(cfg.get("max_lease_ttl_seconds") or 0)
    if ttl < 30 or max_ttl < ttl:
        raise GatewayConfigError("租约 TTL 配置非法（需 >=30s 且不超过 max_lease_ttl_seconds）")
    overrides = cfg.get("tenant_lease_ttl_seconds")
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise GatewayConfigError("gateway.tenant_lease_ttl_seconds 必须为对象")
        for key, value in overrides.items():
            if ":" not in str(key):
                raise GatewayConfigError(
                    f"gateway.tenant_lease_ttl_seconds 键必须为 owner_type:owner_id: {key}"
                )
            try:
                seconds = int(value)
            except (TypeError, ValueError):
                raise GatewayConfigError(
                    f"gateway.tenant_lease_ttl_seconds 值必须为整数: {key}"
                )
            if seconds < 30 or seconds > max_ttl:
                raise GatewayConfigError(
                    f"gateway.tenant_lease_ttl_seconds 值需在 30-{max_ttl}s: {key}"
                )
    if int(cfg.get("max_rpm") or 0) <= 0:
        raise GatewayConfigError("gateway.max_rpm 必须为正整数")
    try:
        if int(cfg.get("retry_max_attempts") or 0) < 1:
            raise ValueError("retry_max_attempts 必须 >= 1")
        statuses = cfg.get("retry_statuses")
        if not isinstance(statuses, (list, tuple)) or not statuses:
            raise ValueError("retry_statuses 必须为非空列表")
        for status in statuses:
            if not isinstance(status, int) or not 400 <= status <= 599:
                raise ValueError(f"retry_statuses 含非法状态码: {status}")
        if float(cfg.get("total_timeout_seconds") or 0) < 0:
            raise ValueError("total_timeout_seconds 不能为负数")
        if int(cfg.get("max_connections") or 0) < 1:
            raise ValueError("max_connections 必须 >= 1")
    except (TypeError, ValueError) as exc:
        raise GatewayConfigError(f"gateway 上游传输配置非法: {exc}")
    return cfg


def validate_gateway_config() -> Dict[str, Any]:
    """L3 网关启动校验：数据面配置 + 固定拒绝 env fallback/直连。"""
    cfg = gateway_config()
    if not cfg.get("enabled"):
        return cfg
    try:
        if read_env_value("GW_ALLOW_ENV_FALLBACK", "bool", default=False):
            raise GatewayConfigError(
                "网关模式下禁止 GW_ALLOW_ENV_FALLBACK=true（不得退回环境变量 provider key）"
            )
        if read_env_value("GW_ALLOW_DIRECT_PROVIDER", "bool", default=False):
            raise GatewayConfigError(
                "网关模式下禁止 GW_ALLOW_DIRECT_PROVIDER=true（不得使用内置 key 直连 provider）"
            )
    except ConfigError as exc:
        raise GatewayConfigError(str(exc)) from exc
    return _validate_fail_closed(cfg)
