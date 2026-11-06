from fastapi import APIRouter
from base.common.setting import settings
from base.common.response import success_response

router = APIRouter(prefix="/v1/common", tags=["公共配置"])


def _get_enabled_plugins() -> list[str]:
    """读取各插件 manifest 的 is_enabled 状态，返回启用插件名列表"""
    import json
    from pathlib import Path

    plugins_dir = settings.base_path / "base" / "plugins"
    enabled: list[str] = []
    if not plugins_dir.exists():
        return enabled
    for plugin_dir in plugins_dir.iterdir():
        manifest = plugin_dir / "manifest.json"
        if not plugin_dir.is_dir() or not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
            if m.get("is_enabled"):
                enabled.append(plugin_dir.name)
        except Exception:
            continue
    return enabled


@router.get("/system-config", summary="获取系统公共配置")
async def get_system_config():
    """获取前端可公开的系统配置（无需登录）"""
    return success_response({
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "app_description": settings.app_description,
        "frontend_name": settings.frontend_name,
        "backend_name": settings.backend_name,
        "debug": settings.debug,
        "install_redirect": settings.install_redirect,
        "enabled_plugins": _get_enabled_plugins(),
    })
