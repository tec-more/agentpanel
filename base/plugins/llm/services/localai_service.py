"""
OpenAI大模型服务
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


class LocalAIService:
    """本地AI大模型服务类"""

    def __init__(self, api_key: str, endpoint_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.endpoint_url = endpoint_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def _policy(self):
        # 本地 provider 显式允许回环/私网地址
        return egress_policy("local", self.endpoint_url)

    async def chat(self, model: str, messages: List[Dict],
                   temperature: float = 0.7, max_tokens: int = 2000,
                   top_p: float = 0.9, stream: bool = False,
                   stop: List[str] = None) -> Dict:
        """非流式聊天"""
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
            await ensure_success(response, label="OpenAI API调用失败")
            return response.json()
        except UpstreamStatusError as e:
            logger.error(f"OpenAI API错误: {e.status_code} - {e.body_text}")
            raise Exception(f"OpenAI API调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"OpenAI服务异常: {str(e)}")
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
            await ensure_success(response, label="OpenAI流式调用失败")

            async for data_str in iter_sse_data(response):
                try:
                    yield json.loads(data_str)
                except json.JSONDecodeError:
                    logger.warning(f"无法解析SSE数据: {data_str}")
                    continue
        except UpstreamStatusError as e:
            logger.error(f"OpenAI流式API错误: {e.status_code}")
            raise Exception(f"OpenAI流式调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"OpenAI流式服务异常: {str(e)}")
            raise
        finally:
            if response is not None:
                await response.aclose()

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量"""
        # 英文约4字符/token，中文约1.5字符/token
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)

    async def create_embedding(self, model: str, text: str) -> List[float]:
        """创建文本向量（Embedding）"""
        url = f"{self.endpoint_url}/embeddings"

        payload = {
            "model": model,
            "input": text,
            "encoding_format": "float"
        }

        try:
            response = await post_json(
                url,
                headers=self.headers,
                json=payload,
                cfg=chat_config(),
                policy=self._policy(),
            )
            await ensure_success(response, label="OpenAI Embedding调用失败")
            result = response.json()
            return result["data"][0]["embedding"]
        except UpstreamStatusError as e:
            logger.error(f"OpenAI Embedding API错误: {e.status_code} - {e.body_text}")
            raise Exception(f"OpenAI Embedding调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"OpenAI Embedding服务异常: {str(e)}")
            raise
