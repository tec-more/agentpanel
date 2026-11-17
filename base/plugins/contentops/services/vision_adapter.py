"""VisionAdapter：contentops 侧线上多模态识别抽象层（替代本地 OCR/ASR 模型）。

设计（与 LLMAdapter._call 同构，复用 llm 模块凭证链，不自建 SDK 抽象）：
- 从 contentops_llm_provider_config 读 purpose='vision' 的线上视觉模型配置；
- 凭证/endpoint 解析复用 llm 插件的 LLMModel / LLMApiKey / LLMProvider；
- 用 OpenAI 兼容多模态 messages（image_url=data:...;base64）让视觉模型识别图中文字；
- 强制 region=domestic：禁用海外 provider；
- PII 脱敏 + 失败降级由调用方（media_detection_service）负责，本层抛可读异常。

注意：当前系统若未配置任何视觉模型（llm 模块四表空），本层抛 RuntimeError，
调用方据此把 ocr_status/asr_status 标为 unavailable，不阻塞上传与文本合规检测。
"""
import base64
import mimetypes
from pathlib import Path
from typing import Optional

from base.plugins.contentops.services.llm_adapter import (
    LLMAdapter, OVERSEAS_PROVIDERS, scrub_pii,
)


class VisionAdapter:
    """线上视觉模型识别（图片文字提取），复用 llm 模块。"""

    @staticmethod
    async def is_configured(purpose: str = "vision") -> bool:
        """判断是否有启用的视觉模型配置（只读配置表，不解析凭证）。"""
        from base.plugins.contentops.models import LLMProviderConfig
        return await LLMProviderConfig.filter(purpose=purpose, enabled=True).exists()

    @staticmethod
    async def _resolve_service(purpose: str = "vision"):
        """解析视觉模型配置 + llm 模块凭证，返回 (service, model_id, meta)。失败抛 RuntimeError。"""
        from base.plugins.llm.models.model import LLMModel
        from base.plugins.llm.models.api_key import LLMApiKey
        from base.plugins.llm.models.provider import LLMProvider
        from base.plugins.llm.services.chat_service import ChatService
        from base.plugins.contentops.models import LLMProviderConfig

        cfg = await LLMProviderConfig.filter(purpose=purpose, enabled=True).first()
        if not cfg:
            raise RuntimeError(
                f"未配置线上视觉模型（LLMProviderConfig purpose='{purpose}'），"
                "请在 llm 模块配置支持视觉的模型（如 qwen-vl / doubao-vision）"
            )
        provider_name = cfg.provider
        if provider_name.lower() in OVERSEAS_PROVIDERS:
            raise ValueError(f"VisionAdapter 强制 region=domestic，已禁用海外 provider: {provider_name}")

        model = await LLMModel.filter(model_id=cfg.model).first()
        if not model:
            try:
                model = await LLMModel.get_or_none(id=int(cfg.model))
            except (ValueError, TypeError):
                pass
        if not model:
            raise RuntimeError(f"视觉模型不存在: {cfg.model}")
        provider = await LLMProvider.get_or_none(id=model.provider_id) if hasattr(model, "provider_id") else None
        if not provider and hasattr(model, "provider"):
            await model.fetch_related("provider")
            provider = model.provider
        if not provider:
            raise RuntimeError("视觉模型供应商不存在")

        api_key_obj = await LLMApiKey.filter(model_id=model.model_id).first()
        if not api_key_obj:
            raise RuntimeError("视觉模型无可用 API 密钥")

        endpoint_url = cfg.endpoint or model.endpoint_url or api_key_obj.endpoint_url or provider.official_url
        if endpoint_url:
            endpoint_url = endpoint_url.rstrip("/")
            if endpoint_url.endswith("/chat/completions"):
                endpoint_url = endpoint_url[:-len("/chat/completions")]
            if "/responses" in endpoint_url:
                endpoint_url = endpoint_url.split("/responses")[0]

        credentials = api_key_obj.get_credentials()
        service = await ChatService.get_provider_service(
            provider_name_en=provider.name_en,
            api_key=credentials.get("api_key", ""),
            api_secret=credentials.get("api_secret"),
            endpoint_url=endpoint_url or "",
            call_mode=getattr(api_key_obj, "call_mode", "vendor_sdk") or "vendor_sdk",
        )
        meta = {"provider": provider.name_en, "model": model.model_id}
        return service, model.model_id, meta

    @staticmethod
    async def recognize_image(
        path: Path,
        purpose: str = "vision",
        instruction: Optional[str] = None,
    ) -> tuple[str, dict]:
        """识别单张图片中的文字，返回 (文字, 调用元数据)。失败抛可读异常。"""
        service, model_id, meta = await VisionAdapter._resolve_service(purpose)
        data = Path(path).read_bytes()
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "image/jpeg"
        b64 = base64.b64encode(data).decode("ascii")
        sys_prompt = instruction or (
            "你是图片文字识别助手。请逐字提取图片中出现的所有文字，按阅读顺序输出，"
            "保留原始行结构；只输出识别到的文字，不要解释、不要描述图片内容。若图片无文字则输出空字符串。"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": "请提取这张图片中的全部文字："},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ]
        result = await service.chat(
            model=model_id, messages=messages,
            temperature=0.0, stream=False,
        )
        text = result["choices"][0]["message"]["content"] or ""
        meta["pii_scrubbed"] = False
        safe = scrub_pii(text)
        meta["pii_scrubbed"] = safe != text
        return safe, meta
