"""
腾讯混元大模型服务
"""
import json
import httpx
from typing import AsyncIterator, List, Dict
import logging
import time
import hashlib

logger = logging.getLogger(__name__)


class TencentService:
    """腾讯混元大模型服务类"""

    def __init__(self, api_key: str, api_secret: str = None,
                 endpoint_url: str = "https://hunyuan.tencentcloudapi.com"):
        self.api_key = api_key
        self.api_secret = api_secret or ""
        self.endpoint_url = endpoint_url
        self.service = "hunyuan"
        self.version = "2023-09-01"
        self.host = "hunyuan.tencentcloudapi.com"

    def _sign(self, payload: str, timestamp: int) -> str:
        """生成腾讯云API签名"""
        # 简化版签名，实际生产需要完整的TC3-HMAC-SHA1签名
        secret_id = self.api_key
        secret_key = self.api_secret

        # 这里简化处理，实际应该使用腾讯云SDK
        # 返回一个简化的签名
        return f"TC3-HMAC-SHA256 Credential={secret_id}/{timestamp}/{self.service}/tc3_request"

    async def chat(self, model: str, messages: List[Dict],
                   temperature: float = 0.7, max_tokens: int = 2000,
                   top_p: float = 0.9, stream: bool = False,
                   stop: List[str] = None) -> Dict:
        """非流式聊天"""
        url = f"https://{self.host}/"

        # 腾讯云格式
        timestamp = int(time.time())
        payload_json = json.dumps({
            "Model": model,
            "Messages": messages,
            "Temperature": temperature,
            "TopP": top_p
        })

        headers = {
            "Authorization": self._sign(payload_json, timestamp),
            "Content-Type": "application/json",
            "Host": self.host,
            "X-TC-Action": "ChatCompletions",
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": self.version
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json={
                    "Model": model,
                    "Messages": messages,
                    "Temperature": temperature,
                    "TopP": top_p
                })
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"腾讯API错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"腾讯API调用失败: {e.response.text}")
        except Exception as e:
            logger.error(f"腾讯服务异常: {str(e)}")
            raise

    async def chat_stream(self, model: str, messages: List[Dict],
                          temperature: float = 0.7, max_tokens: int = 2000,
                          top_p: float = 0.9, stop: List[str] = None) -> AsyncIterator[Dict]:
        """流式聊天（腾讯混元暂不支持流式，使用非流式模拟）"""
        result = await self.chat(model, messages, temperature, max_tokens, top_p)
        # 转换为流式格式
        yield {
            "id": result.get("RequestId", ""),
            "choices": [{
                "delta": {"content": result.get("Reply", "")},
                "finish_reason": "stop"
            }]
        }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)
