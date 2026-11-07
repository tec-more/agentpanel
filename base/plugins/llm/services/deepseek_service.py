"""
DeepSeek大模型服务
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


class DeepSeekService:
    """DeepSeek大模型服务类"""

    def __init__(self, api_key: str, endpoint_url: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.endpoint_url = endpoint_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _policy(self):
        return egress_policy("deepseek", self.endpoint_url)

    async def chat(self, model: str, messages: List[Dict],
                   temperature: float = 0.7, max_tokens: int = 2000,
                   top_p: float = 0.9, stream: bool = False,
                   stop: List[str] = None) -> Dict:
        """非流式聊天（兼容OpenAI格式）"""
        url = f"{self.endpoint_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": False
        }

        if stop:
            payload["stop"] = stop

        try:
            response = await post_json(
                url,
                headers=self.headers,
                json=payload,
                cfg=chat_config(),
                policy=self._policy(),
            )
            await ensure_success(response, label="DeepSeek API调用失败")
            return response.json()
        except UpstreamStatusError as e:
            logger.error(f"DeepSeek API错误: {e.status_code} - {e.body_text}")
            raise Exception(f"DeepSeek API调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"DeepSeek服务异常: {str(e)}")
            raise

    async def chat_stream(self, model: str, messages: List[Dict],
                          temperature: float = 0.7, max_tokens: int = 2000,
                          top_p: float = 0.9, stop: List[str] = None) -> AsyncIterator[Dict]:
        """流式聊天"""
        url = f"{self.endpoint_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True
        }

        if stop:
            payload["stop"] = stop

        response = None
        try:
            response = await send_stream(
                url,
                headers=self.headers,
                json=payload,
                cfg=stream_config(),
                policy=self._policy(),
            )
            await ensure_success(response, label="DeepSeek流式调用失败")

            async for data_str in iter_sse_data(response):
                try:
                    yield json.loads(data_str)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析SSE数据: {data_str}")
                    continue
        except UpstreamStatusError as e:
            logger.error(f"DeepSeek流式API错误: {e.status_code}")
            raise Exception(f"DeepSeek流式调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"DeepSeek流式服务异常: {str(e)}")
            raise
        finally:
            if response is not None:
                await response.aclose()

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)
