"""
Harness 模型凭据解析服务（app 兼容层）

解析逻辑已迁至共享 `packages.common.domain.credential_resolver`（P3 C1/T3.5）。
本文件保留：
- app 管理端只读列表 `list_configured()`（CRUD/掩码读留在 app）；
- `configure_app()`：从 harness manifest 惰性注入默认主体 / env fallback / 环境变量名。
"""
from typing import Any, Dict, List, Optional

from base.common.masking import fingerprint, mask_secret
from base.common.plugin_manager import get_plugin_manager
from base.plugins.llm.models.api_key import LLMApiKey
from packages.common.domain import credential_resolver as _shared
from packages.common.domain.credential_resolver import (  # noqa: F401（对外契约）
    LLM_SERVICE_TYPE,
    ModelCredential,
    ModelCredentialNotConfigured,
)

PLUGIN_NAME = "harness"

_app_configured = False


def _harness_config() -> Dict[str, Any]:
    manifest = get_plugin_manager().get_manifest(PLUGIN_NAME) or {}
    config = manifest.get("config") or {}
    return config if isinstance(config, dict) else {}


def _runtime_config() -> Dict[str, Any]:
    runtime = _harness_config().get("runtime") or {}
    return runtime if isinstance(runtime, dict) else {}


def _env_names() -> Dict[str, str]:
    names = _runtime_config().get("env_names") or {}
    return {
        "api_key": names.get("api_key") or "DEEPSEEK_API_KEY",
        "base_url": names.get("base_url") or "DEEPSEEK_BASE_URL",
        "provider": names.get("provider") or "DSH_PROVIDER",
        "model": names.get("model") or "DSH_MODEL",
    }


def _env_fallback_allowed() -> bool:
    return bool(_runtime_config().get("allow_env_fallback", False))


def _credential_defaults() -> Dict[str, Optional[str]]:
    defaults = _harness_config().get("model_credential") or {}
    return {
        "provider": defaults.get("provider") if isinstance(defaults, dict) else None,
        "model": defaults.get("model") if isinstance(defaults, dict) else None,
    }


def configure_app() -> None:
    """从 app manifest 注入共享解析器配置（幂等，首次 resolve/list 前调用）。"""
    global _app_configured
    if _app_configured:
        return
    _shared.configure(
        defaults=_credential_defaults(),
        env_fallback=_env_fallback_allowed(),
        env_names=_env_names(),
    )
    _app_configured = True


class HarnessModelCredentialService:
    @classmethod
    async def resolve(
        cls, provider: Optional[str] = None, model: Optional[str] = None
    ) -> ModelCredential:
        configure_app()
        return await _shared.resolve(provider, model)

    @classmethod
    async def list_configured(cls) -> List[Dict[str, Any]]:
        """管理端只读列表：只返回遮蔽值，不含明文"""
        configure_app()
        keys = await LLMApiKey.filter(model_service_type=LLM_SERVICE_TYPE).prefetch_related(
            "provider", "model"
        ).order_by("id")
        rows: List[Dict[str, Any]] = []
        for key in keys:
            rows.append({
                "api_key_id": key.id,
                "provider": getattr(getattr(key, "provider", None), "name_en", ""),
                "provider_name": getattr(getattr(key, "provider", None), "name", ""),
                "model": key.model.model_id if key.model else None,
                "model_name": key.model.model_name if key.model else None,
                "base_url": key.endpoint_url or (key.model.endpoint_url if key.model else None),
                "api_key": mask_secret(key.api_key) if key.api_key else "",
                "key_fingerprint": fingerprint(key.api_key),
                "status": key.status,
                "is_available": key.is_available,
                "remaining_quota": key.remaining_quota,
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            })
        return rows
