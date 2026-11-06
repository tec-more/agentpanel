"""
阿里云通义千问大模型服务
"""
import json
import httpx
from typing import AsyncIterator, List, Dict
import logging

logger = logging.getLogger(__name__)


class AlibabaService:
    """阿里云通义千问大模型服务类"""

    def __init__(self, api_key: str, endpoint_url: str = "https://dashscope.aliyuncs.com/api/v1"):
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
        """非流式聊天（兼容OpenAI格式）"""
        url = f"{self.endpoint_url}/services/aigc/text-generation/generation"

        payload = {
            "model": model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "result_format": "message"
            }
        }

        if stop:
            payload["parameters"]["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"阿里云API错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"阿里云API调用失败: {e.response.text}")
        except Exception as e:
            logger.error(f"阿里云服务异常: {str(e)}")
            raise

    async def chat_stream(self, model: str, messages: List[Dict],
                          temperature: float = 0.7, max_tokens: int = 2000,
                          top_p: float = 0.9, stop: List[str] = None) -> AsyncIterator[Dict]:
        """流式聊天"""
        url = f"{self.endpoint_url}/services/aigc/text-generation/generation"

        payload = {
            "model": model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "incremental_output": True,
                "result_format": "message"
            }
        }

        if stop:
            payload["parameters"]["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, headers=self.headers, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            chunk = json.loads(line)
                            # 转换为统一格式
                            yield chunk
                        except json.JSONDecodeError:
                            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"阿里云流式API错误: {e.response.status_code}")
            raise Exception(f"阿里云流式调用失败: {e.response.text}")
        except Exception as e:
            logger.error(f"阿里云流式服务异常: {str(e)}")
            raise

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)
