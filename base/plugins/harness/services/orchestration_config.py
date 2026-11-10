"""编排服务配置与启动校验（fail-closed）

- 配置来源：`services/orchestration/manifest.json` 的 `config.orchestration`，
  由 `ORCH_*` 环境变量覆盖；不再经过 `plugin_manager`。
- 默认只监听回环地址；非回环必须显式 allow_remote_bind=true；
- 独立入口仅允许 deployment=standalone；
- 内部接口一律要求服务凭据，不提供匿名开关。
"""
from typing import Any, Dict, List

from packages.common.config import (
    REPO_ROOT,
    ConfigError,
    EnvOverride,
    apply_env_overrides,
    load_manifest,
    manifest_section,
)

PLUGIN_NAME = "harness"
ORCHESTRATION_MANIFEST = REPO_ROOT / "services" / "orchestration" / "manifest.json"

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "deployment": "standalone",
    "host": "127.0.0.1",
    "port": 9100,
    "public_base_url": "http://127.0.0.1:9100",
    "mode": "proxy",
    "write_enabled": True,
    "app_internal_base_url": "http://127.0.0.1:9998",
    "internal_timeout_seconds": 5,
    "internal_allowed_ips": ["127.0.0.1", "::1"],
    "allow_remote_bind": False,
    "policy_in_orchestration": False,
    "reconcile_in_orchestration": False,
    "auth_timestamp_window_seconds": 60,
    "app_service_id": "svc_orchestration",
    "app_service_secret_env": "ORCHESTRATION_SERVICE_SECRET",
    "schema_min_version": "",
}

ORCH_ENV_OVERRIDES: tuple[EnvOverride, ...] = (
    EnvOverride("enabled", "ORCH_ENABLED", "bool"),
    EnvOverride("host", "ORCH_HOST", "str"),
    EnvOverride("port", "ORCH_PORT", "int"),
    EnvOverride("public_base_url", "ORCH_PUBLIC_BASE_URL", "str"),
    EnvOverride("app_internal_base_url", "ORCH_APP_BASE_URL", "str"),
    EnvOverride("app_service_id", "ORCH_APP_SERVICE_ID", "str"),
    EnvOverride("internal_timeout_seconds", "ORCH_INTERNAL_TIMEOUT_SECONDS", "int"),
    EnvOverride("write_enabled", "ORCH_WRITE_ENABLED", "bool"),
    EnvOverride("auth_timestamp_window_seconds", "ORCH_AUTH_TIMESTAMP_WINDOW_SECONDS", "int"),
    EnvOverride("internal_allowed_ips", "ORCH_INTERNAL_ALLOWED_IPS", "list"),
    EnvOverride("allow_remote_bind", "ORCH_ALLOW_REMOTE_BIND", "bool"),
    EnvOverride("schema_min_version", "ORCH_SCHEMA_MIN_VERSION", "str"),
)

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class OrchestrationConfigError(RuntimeError):
    """编排配置不满足 fail-closed 约束"""


def orchestration_config() -> Dict[str, Any]:
    """独立 manifest 默认值 + ORCH_* 环境变量覆盖。"""
    manifest = load_manifest(ORCHESTRATION_MANIFEST)
    raw = manifest_section(manifest, "orchestration")
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
    try:
        cfg = apply_env_overrides(cfg, ORCH_ENV_OVERRIDES, source="orchestration")
    except ConfigError as exc:
        raise OrchestrationConfigError(str(exc)) from exc
    return cfg


def is_loopback(host: str) -> bool:
    return str(host or "").strip().lower() in LOOPBACK_HOSTS


def internal_allowed_ips() -> List[str]:
    raw = orchestration_config().get("internal_allowed_ips") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(item).strip() for item in raw if str(item).strip()]


def auth_timestamp_window_seconds() -> int:
    try:
        value = int(orchestration_config().get("auth_timestamp_window_seconds") or 60)
    except (TypeError, ValueError):
        value = 60
    return max(30, min(300, value))


def write_enabled() -> bool:
    return bool(orchestration_config().get("write_enabled"))


def validate_orchestration_config() -> Dict[str, Any]:
    """启动时校验；不合规直接拒绝启动。"""
    cfg = orchestration_config()

    if not cfg.get("enabled"):
        raise OrchestrationConfigError("orchestration.enabled=false，独立编排入口不启动")

    deployment = str(cfg.get("deployment") or "")
    if deployment != "standalone":
        raise OrchestrationConfigError(
            f"当前 orchestration.deployment={deployment}；独立入口仅在 standalone 下启动"
        )

    host = str(cfg.get("host") or "").strip()
    if not host:
        raise OrchestrationConfigError("orchestration.host 不能为空")
    if not is_loopback(host) and not bool(cfg.get("allow_remote_bind")):
        raise OrchestrationConfigError(
            f"orchestration.host={host} 非回环地址；如确需对外监听必须显式 allow_remote_bind=true"
        )

    try:
        port = int(cfg.get("port") or 0)
    except (TypeError, ValueError):
        raise OrchestrationConfigError("orchestration.port 必须为整数")
    if not 1 <= port <= 65535:
        raise OrchestrationConfigError("orchestration.port 必须在 1-65535")

    mode = str(cfg.get("mode") or "")
    if mode not in ("app", "proxy"):
        raise OrchestrationConfigError("orchestration.mode 仅支持 app/proxy")

    for key in ("public_base_url", "app_internal_base_url"):
        url = str(cfg.get(key) or "").strip()
        if not url.startswith(("http://", "https://")):
            raise OrchestrationConfigError(f"orchestration.{key} 必须显式配置为 http(s) 地址")

    allowed = internal_allowed_ips()
    if not allowed:
        raise OrchestrationConfigError("orchestration.internal_allowed_ips 不能为空")

    timeout = cfg.get("internal_timeout_seconds")
    try:
        if float(timeout) <= 0:
            raise ValueError
    except (TypeError, ValueError):
        raise OrchestrationConfigError("orchestration.internal_timeout_seconds 必须为正数")

    return cfg
