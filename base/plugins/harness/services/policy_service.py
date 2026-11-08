"""兼容 shim：实现已迁至共享包 `packages.agentpanel_common.domain.policy_service`。

L2 在启动生命周期内通过 `configure_l2()` 把 manifest 读取器显式注入共享实现，
共享包因此不再依赖 `plugin_manager`（C4）。
"""
from packages.agentpanel_common.domain.policy_service import *  # noqa: F401,F403
from packages.agentpanel_common.domain.policy_service import configure_approval

PLUGIN_NAME = "harness"


def configure_l2() -> None:
    """显式注入 manifest 审批配置与审批插件可用性（由 harness on_startup 调用）。"""
    from base.common.plugin_manager import plugin_manager

    def _approval_config():
        manifest = plugin_manager.get_manifest(PLUGIN_NAME) or {}
        return (manifest.get("config") or {}).get("approval") or {}

    def _approval_channel() -> bool:
        manifest = plugin_manager.get_manifest("approval") or {}
        return bool(manifest.get("is_installed") and manifest.get("is_enabled"))

    configure_approval(config_provider=_approval_config, channel_provider=_approval_channel)
