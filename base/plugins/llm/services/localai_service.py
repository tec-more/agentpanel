"""
OpenAI大模型服务
"""
import json
import httpx
from typing import AsyncIterator, List, Dict
import logging

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
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"OpenAI API调用失败: {e.response.text}")
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

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=self.headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.strip() or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                            yield chunk
                        except json.JSONDecodeError:
                            logger.warning(f"无法解析SSE数据: {data_str}")
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI流式API错误: {e.response.status_code}")
            raise Exception(f"OpenAI流式调用失败: {e.response.text}")
        except Exception as e:
            logger.error(f"OpenAI流式服务异常: {str(e)}")
            raise

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
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return result["data"][0]["embedding"]
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI Embedding API错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"OpenAI Embedding调用失败: {e.response.text}")
        except Exception as e:
            logger.error(f"OpenAI Embedding服务异常: {str(e)}")
            raise
