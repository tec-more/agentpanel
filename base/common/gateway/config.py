"""
内部网关（数据面）配置与启动校验

溯源：已确认架构——桌面端只拿 agentpanel 签发的短期租约虚拟 key，经网关换成
真实 provider key 转发；业务 API 不承载模型流量。

fail-closed 落实：
- gateway.enabled=true 时 gateway.fail_closed 必须为 true；
- runtime.allow_env_fallback / runtime.allow_direct_provider 必须为 false；
- public_base_url 与 provider 域名白名单必须显式配置；
- 部署形态 deployment=standalone|embedded（默认 standalone：由 `python -m base.common.gateway.server`
  作为 L3 独立进程对外服务；embedded 可选退回，随业务 API 挂载到 /v1/gateway）。
"""
from typing import Any, Dict, List

from base.common.plugin_manager import plugin_manager
from base.common.upstream import UpstreamConfig

PLUGIN_NAME = "harness"

# 网关对账（记账 vs 客户端上报）默认阈值；可在 manifest 的
# config.gateway.reconciliation 覆盖。对账不属于数据面 fail-closed 通道，
# 非法配置只告警并回退默认值。
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


class GatewayConfigError(RuntimeError):
    """网关配置不满足 fail-closed 约束"""


def harness_config() -> Dict[str, Any]:
    manifest = plugin_manager.get_manifest(PLUGIN_NAME) or {}
    return manifest.get("config") or {}


def runtime_config() -> Dict[str, Any]:
    return harness_config().get("runtime") or {}


def gateway_config() -> Dict[str, Any]:
    raw = harness_config().get("gateway") or {}
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
    return cfg


def gateway_enabled() -> bool:
    return bool(gateway_config().get("enabled"))


def lease_ttl_override(
    cfg: Dict[str, Any], owner_type: Any, owner_id: Any
) -> Any:
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


def reconciliation_config() -> Dict[str, Any]:
    """合并对账默认配置并做轻量校验；非法项回退默认值（不阻断启动）。"""
    raw = gateway_config().get("reconciliation")
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


def validate_gateway_config() -> Dict[str, Any]:
    """启动时校验；不满足 fail-closed 直接拒绝启动。"""
    cfg = gateway_config()
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
