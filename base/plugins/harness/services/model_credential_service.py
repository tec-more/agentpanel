"""
Harness 模型凭据解析服务

- 只从项目自身 LLM 配置（LLMProvider / LLMModel / LLMApiKey）解析；
- 默认不读取进程全局环境变量（仅 manifest 显式 allow_env_fallback=true 时才允许）；
- 缺失/不可用一律 fail-closed，错误消息固定且不含任何密钥；
- 对外只提供 redacted() / fingerprint，明文 key 仅保留在内存对象中。
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tortoise.expressions import Q

from base.common.masking import fingerprint, mask_secret
from base.common.plugin_manager import plugin_manager
from base.plugins.llm.models.api_key import LLMApiKey
from base.plugins.llm.models.model import LLMModel
from base.plugins.llm.models.provider import LLMProvider

PLUGIN_NAME = "harness"
LLM_SERVICE_TYPE = "llm"


class ModelCredentialNotConfigured(Exception):
    """模型凭据缺失或不可用（fail-closed）"""

    def __init__(self, message: str = "未配置模型凭据"):
        self.message = message
        super().__init__(message)


@dataclass
class ModelCredential:
    provider: str
    provider_name: str
    model: str
    model_name: str
    base_url: str
    api_key: str = field(default="", repr=False)
    api_key_id: Optional[int] = None

    def redacted(self) -> Dict[str, Any]:
        """对外安全视图：不包含明文 key"""
        return {
            "api_key_id": self.api_key_id,
            "provider": self.provider,
            "provider_name": self.provider_name,
            "model": self.model,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "api_key": mask_secret(self.api_key),
            "key_fingerprint": fingerprint(self.api_key),
        }


def _harness_config() -> Dict[str, Any]:
    manifest = plugin_manager.get_manifest(PLUGIN_NAME) or {}
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


def _normalize_base_url(value: Optional[str]) -> str:
    return (value or "").strip().rstrip("/")


def _secret_text(value: Optional[str]) -> str:
    return (value or "").strip()


class HarnessModelCredentialService:
    @classmethod
    async def resolve(
        cls, provider: Optional[str] = None, model: Optional[str] = None
    ) -> ModelCredential:
        defaults = _credential_defaults()
        provider_key = (provider or defaults.get("provider") or "").strip()
        model_key = (model or defaults.get("model") or "").strip()

        provider_obj: Optional[LLMProvider] = None
        if provider_key:
            provider_obj = await LLMProvider.filter(status="active").filter(
                Q(name_en__iexact=provider_key) | Q(name__iexact=provider_key)
            ).first()
            if provider_obj is None:
                raise ModelCredentialNotConfigured("未配置模型凭据")

        keys: List[LLMApiKey] = await LLMApiKey.filter(
            model_service_type=LLM_SERVICE_TYPE, status="active"
        ).prefetch_related("provider", "model").order_by("id")

        if provider_obj is not None:
            keys = [k for k in keys if k.provider_id == provider_obj.id]
        keys = [k for k in keys if k.is_available]

        model_obj: Optional[LLMModel] = None
        if model_key:
            model_filter = LLMModel.filter(status="active").filter(
                Q(model_id__iexact=model_key) | Q(model_name__iexact=model_key)
            )
            if provider_obj is not None:
                model_filter = model_filter.filter(provider_id=provider_obj.id)
            models = await model_filter.limit(2)
            if len(models) != 1:
                raise ModelCredentialNotConfigured("模型凭据未指定")
            model_obj = models[0]
            keys = [
                k for k in keys
                if (k.model is not None and k.model.id == model_obj.id) or k.model is None
            ]

        if not keys:
            return await cls._resolve_from_env(provider_key, model_key)

        key, model_obj = await cls._pick_key_and_model(keys, provider_obj, model_obj)
        api_key = _secret_text(key.api_key)
        if not api_key:
            # 不允许空 key 静默继续；显式配置了环境变量兜底时才尝试
            return await cls._resolve_from_env(provider_key, model_key)

        base_url = _normalize_base_url(
            key.endpoint_url or (model_obj.endpoint_url if model_obj else None)
        )
        if not base_url:
            raise ModelCredentialNotConfigured("未配置模型访问地址")

        provider_name = getattr(getattr(key, "provider", None), "name", "") or ""
        provider_name_en = getattr(getattr(key, "provider", None), "name_en", "") or ""
        return ModelCredential(
            provider=provider_name_en or provider_key,
            provider_name=provider_name,
            model=model_obj.model_id if model_obj else "",
            model_name=model_obj.model_name if model_obj else "",
            base_url=base_url,
            api_key=api_key,
            api_key_id=key.id,
        )

    @classmethod
    async def _pick_key_and_model(
        cls,
        keys: List[LLMApiKey],
        provider_obj: Optional[LLMProvider],
        model_obj: Optional[LLMModel],
    ) -> tuple[LLMApiKey, Optional[LLMModel]]:
        # 指定了模型：优先模型绑定的 key，provider 级 key 兜底
        if model_obj is not None:
            for key in keys:
                if key.model is not None and key.model.id == model_obj.id:
                    return key, model_obj
            provider_keys = [k for k in keys if k.model is None]
            if provider_keys:
                return provider_keys[0], model_obj
            raise ModelCredentialNotConfigured("未配置模型凭据")

        # 未指定模型：优先带模型的 key；多个不同模型视为未指定
        model_keys = [k for k in keys if k.model is not None]
        if model_keys:
            model_ids = {k.model.id for k in model_keys}
            if len(model_ids) > 1:
                raise ModelCredentialNotConfigured("模型凭据未指定")
            key = model_keys[0]
            return key, key.model

        # 只剩 provider 级 key，必须能唯一确定模型
        if provider_obj is None:
            provider_ids = {k.provider_id for k in keys}
            if len(provider_ids) != 1:
                raise ModelCredentialNotConfigured("模型凭据未指定")
            provider_obj = keys[0].provider
        models = await LLMModel.filter(provider_id=provider_obj.id, status="active").limit(2)
        if len(models) != 1:
            raise ModelCredentialNotConfigured("模型凭据未指定")
        return keys[0], models[0]

    @classmethod
    async def _resolve_from_env(
        cls, provider_key: str, model_key: str
    ) -> ModelCredential:
        if not _env_fallback_allowed():
            raise ModelCredentialNotConfigured("未配置模型凭据")

        names = _env_names()
        provider = (os.environ.get(names["provider"]) or provider_key or "").strip()
        model = (os.environ.get(names["model"]) or model_key or "").strip()
        api_key = _secret_text(os.environ.get(names["api_key"]))
        base_url = _normalize_base_url(os.environ.get(names["base_url"]))

        if not api_key:
            raise ModelCredentialNotConfigured("未配置模型凭据")
        if not provider or not model:
            raise ModelCredentialNotConfigured("模型凭据未指定")
        if not base_url:
            raise ModelCredentialNotConfigured("未配置模型访问地址")
        return ModelCredential(
            provider=provider,
            provider_name=provider,
            model=model,
            model_name=model,
            base_url=base_url,
            api_key=api_key,
        )

    @classmethod
    async def list_configured(cls) -> List[Dict[str, Any]]:
        """管理端只读列表：只返回遮蔽值，不含明文"""
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
