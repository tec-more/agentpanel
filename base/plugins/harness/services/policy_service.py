"""兼容 shim：实现已迁至共享包 `packages.common.domain.policy_service`。

app 在启动生命周期内通过 `configure_app()` 把 manifest 读取器显式注入共享实现，
共享包因此不再依赖 `plugin_manager`（C4）。
"""
from packages.common.domain.policy_service import *  # noqa: F401,F403
from packages.common.domain.policy_service import configure_approval

PLUGIN_NAME = "harness"


def configure_app() -> None:
    """显式注入 manifest 审批配置与审批插件可用性（由 harness on_startup 调用）。"""
    from base.common.plugin_manager import get_plugin_manager

    def _approval_config():
        manifest = get_plugin_manager().get_manifest(PLUGIN_NAME) or {}
        return (manifest.get("config") or {}).get("approval") or {}

    def _approval_channel() -> bool:
        manifest = get_plugin_manager().get_manifest("approval") or {}
        return bool(manifest.get("is_installed") and manifest.get("is_enabled"))

    configure_approval(config_provider=_approval_config, channel_provider=_approval_channel)
