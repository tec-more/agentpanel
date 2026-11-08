"""
网关配置（L2 唯一实现）：租约签发配置、L3 数据面配置读取、共享运行时注入。

- `issuance_config()`：L2 专用，读 `base/plugins/harness/manifest.json` 的
  `config.gateway_issuance`（租约签发 / 出网策略 / 启停）。
- `gateway_config()`：网关数据面配置，读 `services/l3-gateway/manifest.json` 的
  `config.gateway`，并允许 `GW_*` 环境变量覆盖；**不经过 plugin_manager**。
- `configure_shared_runtime()`：由 L2 启动期显式调用，把配置/上游/租约缓存 TTL
  provider 注入 `packages.agentpanel_common.gateway.runtime`。

fail-closed 语义保持不变：enabled 时 fail_closed 必须为 true、public_base_url 必须
http(s)、provider 白名单非空、TTL/重试/连接池配置合法。
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

PLUGIN_NAME = "harness"
GATEWAY_MANIFEST = REPO_ROOT / "services" / "l3-gateway" / "manifest.json"

# 网关对账默认阈值（L2 执行对账）
RECONCILE_DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "interval_seconds": 600,
    "window_hours": 24,
    "max_window_hours": 168,
    "diff_amount_high": 1000.0,
    "diff_rate_high": 0.10,
    "diff_cost_high": 1.0,
    "missing_amount_high": 1000.0,
    "duplicate_ratio_high": 2.0,
}

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
    "reconciliation": RECONCILE_DEFAULTS,
}

# 数据面环境变量覆盖（§5.4）
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


def _l2_harness_config() -> Dict[str, Any]:
    """仅 L2 使用：读插件 manifest（延迟导入 plugin_manager，避免 L3 依赖）。"""
    from base.common.plugin_manager import plugin_manager

    manifest = plugin_manager.get_manifest(PLUGIN_NAME) or {}
    return manifest.get("config") or {}


def runtime_config() -> Dict[str, Any]:
    """L2 运行时配置（仅 L2 校验使用）。"""
    return _l2_harness_config().get("runtime") or {}


def issuance_config() -> Dict[str, Any]:
    """L2：租约签发 / 出网策略 / 启停 / 对账（来自 harness manifest）。"""
    raw = _l2_harness_config().get("gateway_issuance") or {}
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
    return cfg


def gateway_config() -> Dict[str, Any]:
    """L3 网关数据面：独立 manifest 默认值 + GW_* 环境变量覆盖。"""
    manifest = load_manifest(GATEWAY_MANIFEST)
    raw = manifest_section(manifest, "gateway")
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
    try:
        cfg = apply_env_overrides(cfg, _GATEWAY_ENV_OVERRIDES, source="gateway")
    except ConfigError as exc:
        raise GatewayConfigError(str(exc)) from exc
    return cfg


def gateway_enabled() -> bool:
    """L2 启停判断（租约签发/运行时启动）。"""
    return bool(issuance_config().get("enabled"))


def lease_ttl_override(cfg: Dict[str, Any], owner_type: Any, owner_id: Any) -> Any:
    """按租户（owner_type:owner_id）读取 TTL 覆盖值；未命中返回 None。"""
    if not owner_type or owner_id is None:
        return None
    overrides = cfg.get("tenant_lease_ttl_seconds") or {}
    if not isinstance(overrides, dict):
        return None
    return overrides.get(f"{owner_type}:{owner_id}")


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


def configure_shared_runtime() -> None:
    """把 L2 的网关配置注入共享网关模块（P4 B：启动期显式装配）。

    共享模块（router/service/budget/lease_auth）不 import `base.*`，
    由 L2 启动期显式调用本函数一次。
    """
    from packages.agentpanel_common.gateway import runtime as _runtime

    _runtime.configure(
        config_provider=gateway_config,
        upstream_provider=gateway_upstream_config,
        lease_ttl_provider=lambda cfg=None: lease_cache_ttl_seconds(cfg or gateway_config()),
    )


def reconciliation_config() -> Dict[str, Any]:
    """合并对账默认配置并做轻量校验；非法项回退默认值（不阻断启动）。L2 使用。"""
    raw = issuance_config().get("reconciliation")
    cfg = dict(RECONCILE_DEFAULTS)
    if isinstance(raw, dict):
        cfg.update({k: v for k, v in raw.items() if v is not None})

    defaults = RECONCILE_DEFAULTS
    try:
        interval = int(cfg.get("interval_seconds"))
        if interval < 30:
            raise ValueError("interval_seconds 必须 >= 30")
        window = float(cfg.get("window_hours"))
        max_window = float(cfg.get("max_window_hours"))
        if window <= 0:
            raise ValueError("window_hours 必须为正数")
        if max_window < window:
            raise ValueError("max_window_hours 不能小于 window_hours")
        thresholds = {
            key: float(cfg.get(key))
            for key in (
                "diff_amount_high", "diff_rate_high", "diff_cost_high",
                "missing_amount_high", "duplicate_ratio_high",
            )
        }
        if any(v < 0 for v in thresholds.values()):
            raise ValueError("对账阈值不能为负数")
        if thresholds["duplicate_ratio_high"] < 1:
            raise ValueError("duplicate_ratio_high 必须 >= 1")
    except (TypeError, ValueError) as exc:
        print(f"[gateway] 对账配置非法，回退默认值: {exc}")
        return dict(defaults)

    cfg["enabled"] = bool(cfg.get("enabled"))
    cfg["interval_seconds"] = interval
    cfg["window_hours"] = window
    cfg["max_window_hours"] = max_window
    cfg.update(thresholds)
    return cfg


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


def validate_issuance_config() -> Dict[str, Any]:
    """L2 启动校验：租约签发/出网配置（来自 harness manifest）。"""
    cfg = issuance_config()
    if not cfg.get("enabled"):
        return cfg
    runtime = runtime_config()
    if runtime.get("allow_env_fallback"):
        raise GatewayConfigError(
            "网关模式下禁止 runtime.allow_env_fallback=true（不得退回环境变量 provider key）"
        )
    if runtime.get("allow_direct_provider"):
        raise GatewayConfigError(
            "网关模式下禁止 runtime.allow_direct_provider=true（不得使用内置 key 直连 provider）"
        )
    return _validate_fail_closed(cfg)
