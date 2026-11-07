"""
百度文心大模型服务
"""
import json
from typing import AsyncIterator, List, Dict
import logging

from base.common.upstream import (
    UpstreamStatusError,
    ensure_success,
    get_json,
    post_json,
    send_stream,
)
from base.plugins.llm.services.upstream_helpers import (
    chat_config,
    egress_policy,
    stream_config,
)

logger = logging.getLogger(__name__)


class BaiduService:
    """百度文心大模型服务类"""

    def __init__(self, api_key: str, api_secret: str,
                 endpoint_url: str = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.endpoint_url = endpoint_url
        self.access_token = None

    def _policy(self):
        return egress_policy("baidu", self.endpoint_url)

    async def _get_access_token(self) -> str:
        """获取百度access token"""
        if self.access_token:
            return self.access_token

        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.api_key}&client_secret={self.api_secret}"

        response = await get_json(
            url,
            cfg=chat_config(),
            policy=self._policy(),
        )
        await ensure_success(response, label="百度 access token")
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
            response = await post_json(
                url,
                json=payload,
                cfg=chat_config(),
                policy=self._policy(),
            )
            await ensure_success(response, label="百度API调用失败")
            return response.json()
        except UpstreamStatusError as e:
            logger.error(f"百度API错误: {e.status_code} - {e.body_text}")
            raise Exception(f"百度API调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"百度服务异常: {str(e)}")
            raise

    async def chat_stream(self, model: str, messages: List[Dict],
                          temperature: float = 0.7, max_tokens: int = 2000,
                          top_p: float = 0.9, stop: List[str] = None) -> AsyncIterator[Dict]:
        """流式聊天（逐行 JSON）"""
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

        response = None
        try:
            response = await send_stream(
                url,
                json=payload,
                cfg=stream_config(),
                policy=self._policy(),
            )
            await ensure_success(response, label="百度流式调用失败")

            async for line in response.aiter_lines():
                if not line.strip():
                    continue

                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        except UpstreamStatusError as e:
            logger.error(f"百度流式API错误: {e.status_code}")
            raise Exception(f"百度流式调用失败: {e.body_text}")
        except Exception as e:
            logger.error(f"百度流式服务异常: {str(e)}")
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
