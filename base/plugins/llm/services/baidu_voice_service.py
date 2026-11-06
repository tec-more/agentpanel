"""
百度语音服务 - 语音识别 + 语音合成 + 短语音识别
"""
import json
import httpx
from typing import AsyncIterator, Dict
import logging
import asyncio

logger = logging.getLogger(__name__)


class BaiduVoiceService:
    """百度语音服务类"""

    def __init__(self, api_key: str, api_secret: str,
                 endpoint_url: str = "https://aip.baidubce.com"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.endpoint_url = endpoint_url
        self.access_token = None

    async def _get_access_token(self) -> str:
        """获取百度access token"""
        if self.access_token:
            return self.access_token

        url = f"{self.endpoint_url}/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            result = response.json()
            self.access_token = result.get("access_token")
            return self.access_token

    async def streaming_asr(self, audio_data: bytes, format: str = "wav",
                            sample_rate: int = 16000, language: str = "zh") -> AsyncIterator[Dict]:
        """
        百度实时语音识别
        """
        token = await self._get_access_token()
        url = f"{self.endpoint_url}/rpc/2.0/aasr/v1/create"

        # 百度实时语音识别使用WebSocket
        # 这里简化处理，使用文件识别模拟
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp:
            tmp.write(audio_data)
            tmp.flush()
            tmp_path = tmp.name

        try:
            result = await self.file_asr(tmp_path, format, sample_rate, language)
            text = result.get("result", [])

            # 模拟流式输出
            full_text = "".join(text)
            chunk_size = 10

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i+chunk_size]
                yield {
                    "text": chunk,
                    "is_final": (i + chunk_size >= len(full_text)),
                    "confidence": 0.95
                }
        finally:
            import os
            os.unlink(tmp_path)

    async def file_asr(self, audio_file: str, format: str = "wav",
                      sample_rate: int = 16000, language: str = "zh") -> Dict:
        """
        百度录音文件识别（语音转文字）
        """
        token = await self._get_access_token()

        # 根据语言选择接口
        if language == "zh":
            url = f"{self.endpoint_url}/rpc/2.0/aasr/v1/recognize"  # 长语音
        else:
            url = f"{self.endpoint_url}/rpc/2.0/aasr/v1/recognize"  # 短语音

        # 读取音频并转为base64
        import base64
        with open(audio_file, 'rb') as f:
            audio_data = f.read()
            audio_base64 = base64.b64encode(audio_data).decode()

        payload = {
            "format": format,
            "rate": sample_rate,
            "cuid": "user_001",
            "token": token,
            "dev_pid": 1737,  # 默认普通话模型
            "speech": audio_base64,
            "len": len(audio_data)
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"百度ASR错误: {str(e)}")
            raise Exception(f"百度ASR失败: {str(e)}")

    async def text_to_speech(self, text: str, voice: int = 0, speed: int = 5,
                             pitch: int = 5, volume: int = 5, format: str = "mp3") -> bytes:
        """
        百度语音合成
        """
        token = await self._get_access_token()
        url = f"{self.endpoint_url}/rpc/2.0/tts/v1/create"

        payload = {
            "tex": text,
            "tok": token,
            "ctp": 1,  # 音频格式：3为mp3，1为wav
            "spd": speed,  # 语速0-15
            "pit": pitch,  # 音调0-15
            "vol": volume,  # 音量0-15
            "aue": 3 if format == "mp3" else 1,  # 格式
            "per": 1  # 人：0为女声，1为男声
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                # 百度返回JSON，需要获取音频文件
                if result.get("errno") == 0 and result.get("data"):
                    # 实际音频需要从返回的URL下载
                    audio_url = result["data"]
                    audio_response = await client.get(audio_url)
                    return audio_response.content
                else:
                    raise Exception(f"TTS失败: {result.get('errmsg')}")

        except Exception as e:
            logger.error(f"百度TTS错误: {str(e)}")
            raise Exception(f"百度TTS失败: {str(e)}")

    async def clone_voice(self, reference_audio: str, voice_name: str, **kwargs):
        """百度不支持声音复刻"""
        raise NotImplementedError("百度不支持声音复刻功能")

    async def streaming_translation(self, audio_data: bytes, source_language: str = "zh",
                                    target_language: str = "en", **kwargs) -> AsyncIterator[Dict]:
        """
        百度同声传译（机器翻译）
        """
        # 先进行语音识别
        text = ""
        async for result in self.streaming_asr(audio_data, **kwargs):
            text += result.get("text", "")

        # 然后翻译
        token = await self._get_access_token()
        url = f"{self.endpoint_url}/rpc/2.0/mt/texttrans/v1"

        payload = {
            "q": text,
            "from": source_language,
            "to": target_language,
            "tok": token
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                # 返回翻译结果
                yield {
                    "source_text": text,
                    "target_text": result.get("result", {}).get("trans_result", []),
                    "is_final": True
                }
        except Exception as e:
            logger.error(f"百度翻译错误: {str(e)}")
            raise Exception(f"百度翻译失败: {str(e)}")
