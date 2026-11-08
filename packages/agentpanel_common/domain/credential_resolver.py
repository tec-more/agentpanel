"""模型凭据解析（共享实现，P3 C1 / T3.5）。

- 只从项目自身 LLM 配置（LLMProvider / LLMModel / LLMApiKey）解析；
- 默认不读取进程全局环境变量；仅入口显式 `configure(env_fallback=True)` 时才允许；
- 缺失/不可用一律 fail-closed，错误消息固定且不含任何密钥；
- 对外只提供 redacted() / fingerprint，明文 key 仅保留在内存对象中。
- L2 与 L3 网关使用同一份实现；L2 由 manifest 注入配置，网关禁止 env fallback。
"""
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from tortoise.expressions import Q

from ..masking import fingerprint, mask_secret
from ..models.llm_api_key import LLMApiKey
from ..models.llm_model import LLMModel
from ..models.llm_provider import LLMProvider

LLM_SERVICE_TYPE = "llm"

DEFAULT_ENV_NAMES: Dict[str, str] = {
    "api_key": "DEEPSEEK_API_KEY",
    "base_url": "DEEPSEEK_BASE_URL",
    "provider": "DSH_PROVIDER",
    "model": "DSH_MODEL",
}

_defaults: Dict[str, Optional[str]] = {"provider": None, "model": None}
_env_fallback: bool = False
_env_names: Dict[str, str] = dict(DEFAULT_ENV_NAMES)


def configure(*, defaults: Optional[Dict[str, Any]] = None, env_fallback: bool = False,
              env_names: Optional[Dict[str, str]] = None) -> None:
    """注入解析配置。

    Args:
        defaults: {"provider": ..., "model": ...} 默认主体
        env_fallback: 是否允许从进程环境变量兜底（网关必须为 False）
        env_names: 环境变量名映射
    """
    global _defaults, _env_fallback, _env_names
    if defaults is not None:
        _defaults = {
            "provider": (defaults.get("provider") if isinstance(defaults, dict) else None),
            "model": (defaults.get("model") if isinstance(defaults, dict) else None),
        }
    _env_fallback = bool(env_fallback)
    if env_names:
        _env_names = {**DEFAULT_ENV_NAMES, **env_names}


def env_fallback_allowed() -> bool:
    return _env_fallback


def credential_defaults() -> Dict[str, Optional[str]]:
    return dict(_defaults)


def env_names() -> Dict[str, str]:
    return dict(_env_names)


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


def _normalize_base_url(value: Optional[str]) -> str:
    return (value or "").strip().rstrip("/")


def _secret_text(value: Optional[str]) -> str:
    return (value or "").strip()


async def resolve(provider: Optional[str] = None, model: Optional[str] = None) -> ModelCredential:
    provider_key = (provider or _defaults.get("provider") or "").strip()
    model_key = (model or _defaults.get("model") or "").strip()

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
        return await _resolve_from_env(provider_key, model_key)

    key, model_obj = await _pick_key_and_model(keys, provider_obj, model_obj)
    api_key = _secret_text(key.api_key)
    if not api_key:
        return await _resolve_from_env(provider_key, model_key)

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


async def _pick_key_and_model(
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


async def _resolve_from_env(provider_key: str, model_key: str) -> ModelCredential:
    if not _env_fallback:
        raise ModelCredentialNotConfigured("未配置模型凭据")

    provider = (os.environ.get(_env_names["provider"]) or provider_key or "").strip()
    model = (os.environ.get(_env_names["model"]) or model_key or "").strip()
    api_key = _secret_text(os.environ.get(_env_names["api_key"]))
    base_url = _normalize_base_url(os.environ.get(_env_names["base_url"]))

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
