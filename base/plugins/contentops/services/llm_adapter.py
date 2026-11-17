"""LLMAdapter：contentops 侧统一 AI 改写抽象层。

设计：
- 复用 llm 插件的 ChatService（不自建厂商 SDK 抽象），供应商配置化、可切换。
- 强制 region=domestic：配置层禁用海外 provider（硬约束，不靠自觉）。
- PII 脱敏钩子：送模型前脱敏，审计只记元数据不记正文。
- 失败降级：LLM 不可用时回退到规则模板，保证自适应链路不中断。
"""
import re
from typing import Any, Optional

# 海外 provider 黑名单（强制禁用）
OVERSEAS_PROVIDERS = {"openai", "anthropic", "azure_openai", "google", "gemini"}

# PII 脱敏规则
PII_PATTERNS = [
    (re.compile(r"1[3-9]\d{9}"), "[手机号]"),                      # 手机号
    (re.compile(r"\d{17}[\dXx]"), "[身份证]"),                     # 身份证
    (re.compile(r"\d{16,19}"), "[银行卡]"),                        # 银行卡
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[邮箱]"),          # 邮箱
]


def scrub_pii(text: str) -> str:
    """PII 脱敏：送模型前调用。"""
    for pattern, repl in PII_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class LLMAdapter:
    """统一 AI 能力：rewrite / summarize / topics，走 llm 插件 ChatService。"""

    @staticmethod
    def _resolve_model_ref(provider: str, model: str) -> None:
        """境内节点硬约束：命中海外 provider 直接拒绝。"""
        if provider.lower() in OVERSEAS_PROVIDERS:
            raise ValueError(f"LLMAdapter 强制 region=domestic，已禁用海外 provider: {provider}")

    @staticmethod
    async def _call(content: str, instruction: str, purpose: str = "rewrite") -> tuple[str, dict]:
        """底层统一调用，返回 (输出文本, 调用元数据)。失败抛异常由上层降级。"""
        from base.plugins.llm.models.model import LLMModel
        from base.plugins.llm.models.api_key import LLMApiKey
        from base.plugins.llm.models.provider import LLMProvider
        from base.plugins.llm.services.chat_service import ChatService
        from base.plugins.contentops.models import LLMProviderConfig

        # 1. 读 contentops 的用途配置
        cfg = await LLMProviderConfig.filter(purpose=purpose, enabled=True).first()
        if not cfg:
            raise RuntimeError("未配置可用的 LLM 模型")

        provider_name = cfg.provider
        LLMAdapter._resolve_model_ref(provider_name, cfg.model)

        # 2. 解析 llm 插件的模型与凭证
        model = await LLMModel.filter(model_id=cfg.model).first()
        if not model:
            # cfg.model 可能是 llm 插件的内部 id
            try:
                model = await LLMModel.get_or_none(id=int(cfg.model))
            except (ValueError, TypeError):
                pass
        if not model:
            raise RuntimeError(f"LLM 模型不存在: {cfg.model}")
        provider = await LLMProvider.get_or_none(id=model.provider_id) if hasattr(model, "provider_id") else None
        if not provider and hasattr(model, "provider"):
            await model.fetch_related("provider")
            provider = model.provider
        if not provider:
            raise RuntimeError("LLM 供应商不存在")

        api_key_obj = await LLMApiKey.filter(model_id=model.model_id).first()
        if not api_key_obj:
            raise RuntimeError("LLM 无可用 API 密钥")

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

        # 3. PII 脱敏后送模型
        safe_content = scrub_pii(content)
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": safe_content},
        ]
        result = await service.chat(
            model=model.model_id, messages=messages,
            temperature=0.7, stream=False,
        )
        output = result["choices"][0]["message"]["content"]
        meta = {"provider": provider.name_en, "model": model.model_id, "pii_scrubbed": safe_content != content}
        return output, meta

    @staticmethod
    async def rewrite(text: str, platform: str, rules: str = "") -> tuple[str, dict]:
        instruction = (
            f"你是自媒体内容改写助手。将下文改写为适合【{platform}】平台调性的版本，"
            "保留核心信息与关键词，遵守合规要求。仅输出改写后的正文，不要解释。"
        )
        if rules:
            instruction += f"\n额外要求：{rules}"
        return await LLMAdapter._call(text, instruction, purpose="rewrite")

    @staticmethod
    async def summarize(text: str, max_len: int = 200) -> tuple[str, dict]:
        instruction = f"将下文压缩为不超过 {max_len} 字的摘要，保留核心信息。仅输出摘要。"
        return await LLMAdapter._call(text, instruction, purpose="summarize")

    @staticmethod
    async def topics(text: str, platform: str, limit: int = 5) -> tuple[str, dict]:
        instruction = f"根据下文为【{platform}】平台推荐 {limit} 个话题标签，用逗号分隔输出，不要解释。"
        return await LLMAdapter._call(text, instruction, purpose="topics")
