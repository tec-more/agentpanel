"""
OpenAI语音服务 - Whisper + TTS
"""
import json
import httpx
from typing import AsyncIterator, Dict
import logging

logger = logging.getLogger(__name__)


class OpenAIVoiceService:
    """OpenAI语音服务类（Whisper ASR + TTS）"""

    def __init__(self, api_key: str, endpoint_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.endpoint_url = endpoint_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def streaming_asr(self, audio_data: bytes, format: str = "wav",
                            sample_rate: int = 16000, language: str = "zh") -> AsyncIterator[Dict]:
        """
        OpenAI Whisper 流式语音识别

        注意：OpenAI的Whisper目前不支持流式，这里用模拟实现
        """
        # 先保存临时文件
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp_file:
            tmp_file.write(audio_data)
            tmp_file.flush()
            tmp_path = tmp_file.name

        try:
            # 调用Whisper API
            result = await self.file_asr(tmp_path, format, sample_rate, language)

            # 模拟流式输出
            text = result.get("text", "")
            chunk_size = 10

            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                yield {
                    "text": chunk,
                    "is_final": (i + chunk_size >= len(text)),
                    "confidence": result.get("confidence", 0.95)
                }
        finally:
            os.unlink(tmp_path)

    async def file_asr(self, audio_file: str, format: str = "wav",
                      sample_rate: int = 16000, language: str = "zh") -> Dict:
        """
        OpenAI Whisper 文件语音识别
        """
        url = f"{self.endpoint_url}/audio/transcriptions"

        try:
            # 读取音频文件
            with open(audio_file, 'rb') as f:
                audio_data = f.read()

            # 使用multipart上传
            files = {
                "file": (f"audio.{format}", audio_data, f"audio/{format}")
            }

            data = {
                "model": "whisper-1",
                "language": language,
                "response_format": "verbose_json"
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=self.headers, data=data, files=files)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"OpenAI Whisper错误: {str(e)}")
            raise Exception(f"Whisper识别失败: {str(e)}")

    async def text_to_speech(self, text: str, voice: str = "alloy",
                             speed: float = 1.0, format: str = "mp3") -> bytes:
        """
        OpenAI TTS 语音合成
        """
        url = f"{self.endpoint_url}/audio/speech"

        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": format
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"OpenAI TTS错误: {str(e)}")
            raise Exception(f"TTS失败: {str(e)}")

    async def clone_voice(self, reference_audio: str, voice_name: str, **kwargs):
        """OpenAI不支持声音复刻，抛出异常"""
        raise NotImplementedError("OpenAI不支持声音复刻功能")

    async def streaming_translation(self, audio_data: bytes, **kwargs):
        """OpenAI不支持同声传译，使用两步法（ASR + 翻译）"""
        # 先ASR识别
        text = ""
        async for result in self.streaming_asr(audio_data, **kwargs):
            text += result.get("text", "")

        # 然后翻译（使用ChatGPT）
        # 这里简化处理，实际应该调用翻译API
        yield {
            "source_text": text,
            "target_text": f"[翻译] {text}",  # 占位符
            "is_final": True
        }
