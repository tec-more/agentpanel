"""
阿里云语音服务 - 语音识别 + 语音合成
"""
import json
import httpx
from typing import AsyncIterator, Dict
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


class AlibabaVoiceService:
    """阿里云语音服务类（含有的语音能力）"""

    def __init__(self, api_key: str, endpoint_url: str = "https://nls-meta.cn-hangzhou.aliyuncs.com"):
        self.api_key = api_key
        self.endpoint_url = endpoint_url
        self.app_key = api_key  # 阿里云使用app-key

    async def streaming_asr(self, audio_data: bytes, format: str = "wav",
                            sample_rate: int = 16000, language: str = "zh") -> AsyncIterator[Dict]:
        """
        阿里云实时语音识别
        """
        url = f"{self.endpoint_url}/stream/v1/asr"

        headers = {
            "X-NLS-API-KEY": self.api_key,
            "Content-Type": "application/octet-stream"
        }

        # 使用模拟流式（阿里云支持真正流式，这里简化）
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp:
            tmp.write(audio_data)
            tmp.flush()

        try:
            result = await self.file_asr(tmp.name, format, sample_rate, language)
            text = result.get("output", "").get("result", "")

            # 模拟流式输出
            chunk_size = 10
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                yield {
                    "text": chunk,
                    "is_final": (i + chunk_size >= len(text)),
                    "confidence": 0.95
                }
        finally:
            os.unlink(tmp.name)

    async def file_asr(self, audio_file: str, format: str = "wav",
                      sample_rate: int = 16000, language: str = "zh") -> Dict:
        """
        阿里云录音文件识别
        """
        url = f"{self.endpoint_url}/request/v1/asr"

        # 读取音频文件
        with open(audio_file, 'rb') as f:
            audio_data = f.read()

        # 阿里云使用URL方式，先上传到OSS（这里简化，使用base64）
        import base64
        audio_base64 = base64.b64encode(audio_data).decode()

        payload = {
            "appkey": self.app_key,
            "format": format,
            "sample_rate": sample_rate,
            "enable_punctuation_prediction": True,
            "enable_inverse_text_normalization": True,
            "audio": audio_base64
        }

        headers = {
            "X-NLS-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"阿里云ASR错误: {str(e)}")
            raise Exception(f"阿里云ASR失败: {str(e)}")

    async def text_to_speech(self, text: str, voice: str = "zhichu",
                             speed: float = 1.0, pitch: float = 1.0,
                             volume: float = 1.0, format: str = "mp3") -> bytes:
        """
        阿里云语音合成
        """
        url = f"{self.endpoint_url}/request/v1/tts"

        payload = {
            "appkey": self.app_key,
            "text": text,
            "format": format,
            "sample_rate": 24000,
            "voice": voice,  # 音色
            "rate": int(speed * 100),  # 语速
            "pitch": int(pitch * 100),  # 音调
            "volume": int(volume * 100)  # 音量
        }

        headers = {
            "X-NLS-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                # 阿里云返回二进制音频
                return response.content
        except Exception as e:
            logger.error(f"阿里云TTS错误: {str(e)}")
            raise Exception(f"阿里云TTS失败: {str(e)}")

    async def clone_voice(self, reference_audio: str, voice_name: str, **kwargs):
        """阿里云不支持声音复刻"""
        raise NotImplementedError("阿里云不支持声音复刻功能")

    async def streaming_translation(self, audio_data: bytes, source_language: str = "zh",
                                    target_language: str = "en", **kwargs) -> AsyncIterator[Dict]:
        """
        阿里云翻译
        """
        # 先ASR
        text = ""
        async for result in self.streaming_asr(audio_data, **kwargs):
            text += result.get("text", "")

        # 再翻译
        url = "https://mt.cn-hangzhou.aliyuncs.com/api/translate/web/standard"

        payload = {
            "sourceLanguage": source_language,
            "targetLanguage": target_language,
            "textList": [text],
            "scene": "general"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                yield {
                    "source_text": text,
                    "target_text": result.get("data", {}).get("translatedList", [text])[0],
                    "is_final": True
                }
        except Exception as e:
            logger.error(f"阿里云翻译错误: {str(e)}")
            raise Exception(f"阿里云翻译失败: {str(e)}")
"""
阿里云语音服务
"""
import json
import httpx
from typing import AsyncIterator, Dict
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


class AlibabaVoiceService:
    """阿里云语音服务类"""

    def __init__(self, api_key: str, endpoint_url: str = "https://nls-meta.cn-hangzhou.aliyuncs.com"):
        self.api_key = api_key
        self.endpoint_url = endpoint_url

    async def streaming_asr(self, audio_data: bytes, format: str = "wav",
                            sample_rate: int = 16000, language: str = "zh") -> AsyncIterator[Dict]:
        """阿里云实时语音识别"""
        # 使用文件识别模拟流式
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp:
            tmp.write(audio_data)
            tmp.flush()

        try:
            result = await self.file_asr(tmp.name, format, sample_rate, language)
            text = result.get("output", "").get("result", "")

            # 模拟流式输出
            chunk_size = 10
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                yield {
                    "text": chunk,
                    "is_final": (i + chunk_size >= len(text)),
                    "confidence": 0.95
                }
        finally:
            os.unlink(tmp.name)

    async def file_asr(self, audio_file: str, format: str = "wav",
                      sample_rate: int = 16000, language: str = "zh") -> Dict:
        """阿里云录音文件识别"""
        url = f"{self.endpoint_url}/stream/v1/asr"

        # 读取音频
        with open(audio_file, 'rb') as f:
            audio_data = f.read()

        import base64
        audio_base64 = base64.b64encode(audio_data).decode()

        payload = {
            "format": format,
            "sample_rate": sample_rate,
            "enable_punctuation_prediction": True,
            "audio": audio_base64
        }

        headers = {
            "X-NLS-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"阿里云ASR错误: {str(e)}")
            raise Exception(f"阿里云ASR失败: {str(e)}")

    async def text_to_speech(self, text: str, voice: str = "zhichu",
                             speed: float = 1.0, pitch: float = 1.0,
                             volume: float = 1.0, format: str = "mp3") -> bytes:
        """阿里云语音合成"""
        url = f"{self.endpoint_url}/request/v1/tts"

        payload = {
            "text": text,
            "format": format,
            "sample_rate": 24000,
            "voice": voice,
            "rate": int(speed * 100),
            "pitch": int(pitch * 100),
            "volume": int(volume * 100)
        }

        headers = {
            "X-NLS-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"阿里云TTS错误: {str(e)}")
            raise Exception(f"阿里云TTS失败: {str(e)}")

    async def clone_voice(self, reference_audio: str, voice_name: str, **kwargs):
        """阿里云不支持声音复刻"""
        raise NotImplementedError("阿里云不支持声音复刻功能")

    async def streaming_translation(self, audio_data: bytes, source_language: str = "zh",
                                    target_language: str = "en", **kwargs) -> AsyncIterator[Dict]:
        """阿里云翻译"""
        # 先ASR
        text = ""
        async for result in self.streaming_asr(audio_data, **kwargs):
            text += result.get("text", "")

        # 再翻译
        url = "https://mt.cn-hangzhou.aliyuncs.com/api/translate/web/standard"

        payload = {
            "sourceLanguage": source_language,
            "targetLanguage": target_language,
            "textList": [text],
            "scene": "general"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                yield {
                    "source_text": text,
                    "target_text": result.get("data", {}).get("translatedList", [text])[0],
                    "is_final": True
                }
        except Exception as e:
            logger.error(f"阿里云翻译错误: {str(e)}")
            raise Exception(f"阿里云翻译失败: {str(e)}")
