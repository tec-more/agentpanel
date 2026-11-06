"""
百度文心大模型服务
"""
import json
import httpx
from typing import AsyncIterator, List, Dict
import logging
import time

logger = logging.getLogger(__name__)


class BaiduService:
    """百度文心大模型服务类"""

    def __init__(self, api_key: str, api_secret: str,
                 endpoint_url: str = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.endpoint_url = endpoint_url
        self.access_token = None

    async def _get_access_token(self) -> str:
        """获取百度access token"""
        if self.access_token:
            return self.access_token

        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.api_key}&client_secret={self.api_secret}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            result = response.json()
            self.access_token = result.get("access_token")
            return self.access_token

    async def chat(self, model: str, messages: List[Dict],
                   temperature: float = 0.7, max_tokens: int = 2000,
                   top_p: float = 0.9, stream: bool = False,
                   stop: List[str] = None) -> Dict:
        """非流式聊天"""
        access_token = await self._get_access_token()

        url = f"{self.endpoint_url}?access_token={access_token}"

        # 百度格式
        payload = {
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "penalty_score": 1.0
        }

        if stop:
            payload["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"百度API错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"百度API调用失败: {e.response.text}")
        except Exception as e:
            logger.error(f"百度服务异常: {str(e)}")
            raise

    async def chat_stream(self, model: str, messages: List[Dict],
                          temperature: float = 0.7, max_tokens: int = 2000,
                          top_p: float = 0.9, stop: List[str] = None) -> AsyncIterator[Dict]:
        """流式聊天"""
        access_token = await self._get_access_token()

        url = f"{self.endpoint_url}?access_token={access_token}"

        payload = {
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True
        }

        if stop:
            payload["stop"] = stop

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=payload) as response:
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
            logger.error(f"百度流式API错误: {e.response.status_code}")
            raise Exception(f"百度流式调用失败: {e.response.text}")
        except Exception as e:
            logger.error(f"百度流式服务异常: {str(e)}")
            raise

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)
