"""
M2→M6 LLM 调用统一出口（llm_gateway）

溯源：
- docs/arch/04 §6：llm_call(model_id, messages, stream, ctx) -> AsyncIterator[token] + usage（统一模型出口）
- docs/arch/05 §1.1：超时（默认 60s 可配）→ 重试；429 读取 Retry-After 按 max(Retry-After, 退避) 重试；5xx 退避重试
- docs/arch/06 R-05/R-12：凭证仅调用栈内存使用；禁止落日志/Trace/异常消息

职责边界：本模块只做「单次尝试 + 错误分类」；退避重试编排（1s/2s/4s，上限 3 不可上调）
由引擎节点运行器完成（04-F4），避免两层各自重试导致上限失控。
"""
import asyncio
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from base.common.quota.services.estimator import estimate_messages_tokens, estimate_tokens
from base.plugins.agent.services.engine.errors import NodeExecutionError

# 错误分类正则（供应商包装异常会把状态码带进文本）
_RE_429 = re.compile(r"\b429\b|rate.?limit", re.IGNORECASE)
_RE_5XX = re.compile(r"\b(500|502|503|504)\b")
_RE_4XX = re.compile(r"\b(400|401|403|404|422)\b")
# Retry-After 解析（响应文本/头字符串中的秒数）
_RE_RETRY_AFTER = re.compile(r"retry.?after[^0-9]{0,20}(\d+(?:\.\d+)?)", re.IGNORECASE)

# 节点级超时默认 60s（05-§1.1，可配）
DEFAULT_LLM_TIMEOUT_SECONDS = 60

# token 事件流式回调
TokenCallback = Callable[[str], Awaitable[None]]


def classify_llm_error(exc: Exception) -> NodeExecutionError:
    """
    供应商异常 → 统一 NodeExecutionError 分类

    - timeout → LLM_TIMEOUT（可重试）
    - 429 → LLM_RATE_LIMITED（可重试，携带 retry_after）
    - 5xx → LLM_UPSTREAM_5XX（可重试）
    - 4xx/内容过滤 → LLM_CALL_FAILED（不可重试）
    """
    text = str(exc)
    retry_after = None
    m = _RE_RETRY_AFTER.search(text)
    if m:
        try:
            retry_after = min(float(m.group(1)), 60.0)
        except ValueError:
            retry_after = None
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in text.lower():
        return NodeExecutionError("LLM_TIMEOUT", "模型调用超时", retryable=True)
    if _RE_429.search(text):
        return NodeExecutionError("LLM_RATE_LIMITED", "模型限流(429)", retryable=True,
                                  retry_after=retry_after)
    if _RE_5XX.search(text):
        return NodeExecutionError("LLM_UPSTREAM_5XX", "模型网关 5xx", retryable=True)
    if _RE_4XX.search(text):
        return NodeExecutionError("LLM_CALL_FAILED", "模型调用被拒绝(4xx)", retryable=False)
    # 未知异常按可重试处理（网络抖动等），耗尽后由图策略兜底
    return NodeExecutionError("LLM_CALL_FAILED", "模型调用失败", retryable=True)


def _sanitize_usage(usage: Any, messages: List[Dict], content: str, model: str) -> Dict[str, Any]:
    """usage 归一：优先供应商真实 usage；缺失时字符启发式兜底（03-§2.9）"""
    tokens_in = tokens_out = 0
    if isinstance(usage, dict):
        tokens_in = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    if not tokens_in and not tokens_out:
        tokens_in = estimate_messages_tokens(messages)
        tokens_out = estimate_tokens(content or "")
    return {"tokens_in": tokens_in, "tokens_out": tokens_out, "model": model}


class LLMGateway:
    """LLM 统一出口：模型解析（经 llm 插件通道）+ 单次调用 + 错误分类"""

    @staticmethod
    async def resolve_model(model_ref: Any) -> Dict[str, Any]:
        """
        经 llm 插件现有通道解析模型资源（M6/M7：凭证仅在返回值中内存级传递）

        Returns:
            {provider_name, api_key_str, api_secret, endpoint_url, model_id_for_call, model_name}

        Raises:
            NodeExecutionError(MODEL_UNAVAILABLE, retryable=False)
        """
        from base.plugins.llm.models.model import LLMModel
        from base.plugins.llm.models.provider import LLMProvider
        from base.plugins.llm.models.api_key import LLMApiKey

        model = await LLMModel.get_or_none(id=model_ref, status="active")
        if model is None:
            raise NodeExecutionError("MODEL_UNAVAILABLE", f"模型不存在或未激活: {model_ref}")
        provider = await LLMProvider.get_or_none(id=model.provider_id)
        if provider is None:
            raise NodeExecutionError("MODEL_UNAVAILABLE", f"模型提供者不存在: {model.provider_id}")
        api_key = await LLMApiKey.get_or_none(model_id=model.id)
        if api_key is None:
            raise NodeExecutionError("MODEL_UNAVAILABLE", f"模型 API 密钥未配置: {model.id}")

        endpoint_url = model.endpoint_url or provider.api_endpoint
        if endpoint_url:
            endpoint_url = endpoint_url.rstrip("/")
            if "/responses" in endpoint_url:
                endpoint_url = endpoint_url.split("/responses")[0]
            if endpoint_url.endswith("/chat/completions"):
                endpoint_url = endpoint_url[: -len("/chat/completions")]

        return {
            "provider_name": provider.name_en,
            "api_key_str": api_key.api_key,
            "api_secret": api_key.api_secret,
            "endpoint_url": endpoint_url,
            "model_id_for_call": model.model_id if model.model_id else model.model_name,
            "model_name": model.model_name,
        }

    @staticmethod
    async def _build_service(resource: Dict[str, Any]):
        from base.plugins.llm.services.chat_service import ChatService

        service = await ChatService.get_provider_service(
            provider_name_en=resource["provider_name"],
            api_key=resource["api_key_str"],
            endpoint_url=resource["endpoint_url"],
            api_secret=resource.get("api_secret"),
        )
        if service is None:
            raise NodeExecutionError("MODEL_UNAVAILABLE", "创建聊天服务失败")
        return service

    @classmethod
    async def call(
        cls,
        resource: Dict[str, Any],
        messages: List[Dict[str, Any]],
        *,
        stream: bool = False,
        on_token: Optional[TokenCallback] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout_s: int = DEFAULT_LLM_TIMEOUT_SECONDS,
        trace_id: Any = None,
    ) -> Dict[str, Any]:
        """
        单次 LLM 调用（重试编排由引擎负责）

        Args:
            resource: resolve_model 返回的资源（含凭证，内存级）
            messages: OpenAI 消息格式
            stream: 是否流式
            on_token: 流式 token 回调（SSE token 事件源）
            timeout_s: 节点级超时（默认 60s 可配）
            trace_id: 链路 ID（日志标签，R-12）

        Returns:
            {content, usage: {tokens_in, tokens_out, model}}

        Raises:
            NodeExecutionError: 分类后的统一错误（retryable 标记驱动重试）
        """
        model_for_call = resource["model_id_for_call"]
        try:
            service = await cls._build_service(resource)
            if stream and hasattr(service, "chat_stream"):
                return await cls._call_stream(
                    service, model_for_call, messages, on_token,
                    temperature=temperature, max_tokens=max_tokens,
                )
            response = await asyncio.wait_for(
                service.chat(
                    model=model_for_call,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=timeout_s,
            )
            content, usage = cls._parse_response(response, messages, model_for_call)
            return {"content": content, "usage": usage}
        except NodeExecutionError:
            raise
        except Exception as e:
            logger.warning(f"[llm_gateway] 调用失败 trace_id={trace_id}: {type(e).__name__}")
            raise classify_llm_error(e) from e

    @classmethod
    async def _call_stream(cls, service, model_for_call: str, messages: List[Dict],
                           on_token: Optional[TokenCallback], *,
                           temperature: float, max_tokens: int) -> Dict[str, Any]:
        """流式调用：逐 chunk 回调 token，聚合最终内容与 usage"""
        content_parts: List[str] = []
        usage: Dict[str, Any] = {}
        async for chunk in service.chat_stream(
            model=model_for_call,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if not isinstance(chunk, dict):
                continue
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = (choices[0].get("delta") or {}).get("content") or ""
            if delta:
                content_parts.append(delta)
                if on_token is not None:
                    await on_token(delta)
        content = "".join(content_parts)
        return {"content": content, "usage": _sanitize_usage(usage, messages, content, model_for_call)}

    @staticmethod
    def _parse_response(response: Any, messages: List[Dict], model_for_call: str):
        """非流式响应解析（OpenAI 兼容结构）"""
        content = ""
        usage: Dict[str, Any] = {}
        if isinstance(response, dict):
            usage = response.get("usage") or {}
            choices = response.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                content = message.get("content") or ""
        elif isinstance(response, str):
            content = response
        return content, _sanitize_usage(usage, messages, content, model_for_call)
