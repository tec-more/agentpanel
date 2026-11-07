"""L3 编排服务配置与启动校验（fail-closed）

- 配置来源：manifest `config.orchestration`；
- 默认只监听回环地址；非回环必须显式 allow_remote_bind=true；
- 独立入口仅允许 deployment=standalone；
- 内部接口一律要求服务凭据，不提供匿名开关。
"""
from typing import Any, Dict, List

from base.common.plugin_manager import plugin_manager

PLUGIN_NAME = "harness"

DEFAULTS: Dict[str, Any] = {
    "enabled": True,
    "deployment": "standalone",
    "host": "127.0.0.1",
    "port": 9100,
    "public_base_url": "http://127.0.0.1:9100",
    "mode": "l2",
    "write_enabled": False,
    "l2_internal_base_url": "http://127.0.0.1:9998",
    "internal_timeout_seconds": 5,
    "internal_allowed_ips": ["127.0.0.1", "::1"],
    "allow_remote_bind": False,
    "policy_in_l3": False,
    "reconcile_in_l3": False,
    "auth_timestamp_window_seconds": 60,
    "l2_service_id": "svc_l3_orchestration",
    "l2_service_secret_env": "ORCHESTRATION_SERVICE_SECRET",
}

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


class OrchestrationConfigError(RuntimeError):
    """编排配置不满足 fail-closed 约束"""


def harness_config() -> Dict[str, Any]:
    manifest = plugin_manager.get_manifest(PLUGIN_NAME) or {}
    return manifest.get("config") or {}


def orchestration_config() -> Dict[str, Any]:
    raw = harness_config().get("orchestration") or {}
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in raw.items() if v is not None})
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
    if mode not in ("l2", "proxy_l3"):
        raise OrchestrationConfigError("orchestration.mode 仅支持 l2/proxy_l3")

    for key in ("public_base_url", "l2_internal_base_url"):
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
