"""
Anthropic Claude大模型服务
"""
import json
from typing import AsyncIterator, List, Dict
import logging

from base.common.upstream import (
    UpstreamStatusError,
    ensure_success,
    iter_sse_data,
    post_json,
    send_stream,
)
from base.plugins.llm.services.upstream_helpers import (
    chat_config,
    egress_policy,
    stream_config,
)

logger = logging.getLogger(__name__)


class AnthropicService:
    """Anthropic Claude大模型服务类"""

    def __init__(self, api_key: str, endpoint_url: str = "https://api.anthropic.com/v1"):
        self.api_key = api_key
        self.endpoint_url = endpoint_url.rstrip('/')
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

    def _policy(self):
        return egress_policy("anthropic", self.endpoint_url)

    async def chat(self, model: str, messages: List[Dict],
                   temperature: float = 0.7, max_tokens: int = 2000,
                   top_p: float = 0.9, stream: bool = False,
                   stop: List[str] = None) -> Dict:
        """非流式聊天"""
        url = f"{self.endpoint_url}/messages"

        # Anthropic格式转换
        system_message = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        payload = {
            "model": model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        }

        if system_message:
            payload["system"] = system_message

        if stop:
            payload["stop_sequences"] = stop

        try:
            response = await post_json(
                url,
                headers=self.headers,
                json=payload,
                cfg=chat_config(),
                policy=self._policy(),
            )
            await ensure_success(response, label="Anthropic API调用失败")
            return response.json()
        except UpstreamStatusError as e:
            logger.error(f"Anthropic API错误: {e.status_code} - {e.body_text}")
            raise Exception(f"Anthropic API调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"Anthropic服务异常: {str(e)}")
            raise

    async def chat_stream(self, model: str, messages: List[Dict],
                          temperature: float = 0.7, max_tokens: int = 2000,
                          top_p: float = 0.9, stop: List[str] = None) -> AsyncIterator[Dict]:
        """流式聊天"""
        url = f"{self.endpoint_url}/messages"

        # 格式转换
        system_message = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        payload = {
            "model": model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True
        }

        if system_message:
            payload["system"] = system_message

        if stop:
            payload["stop_sequences"] = stop

        response = None
        try:
            response = await send_stream(
                url,
                headers=self.headers,
                json=payload,
                cfg=stream_config(),
                policy=self._policy(),
            )
            await ensure_success(response, label="Anthropic流式调用失败")

            async for data_str in iter_sse_data(response):
                try:
                    chunk = json.loads(data_str)
                    # 转换为OpenAI格式以保持一致性
                    if "delta" in chunk:
                        yield chunk
                except json.JSONDecodeError:
                    logger.warning(f"无法解析SSE数据: {data_str}")
                    continue
        except UpstreamStatusError as e:
            logger.error(f"Anthropic流式API错误: {e.status_code}")
            raise Exception(f"Anthropic流式调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"Anthropic流式服务异常: {str(e)}")
            raise
        finally:
            if response is not None:
                await response.aclose()

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量（Claude使用更高效的分词）"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        # Claude的token效率略高
        return int(chinese_chars / 1.8 + english_chars / 5)
