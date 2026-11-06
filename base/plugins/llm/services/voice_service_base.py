"""
统一语音服务抽象层
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict
import logging

logger = logging.getLogger(__name__)


class VoiceServiceBase(ABC):
    """语音服务基类"""

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key

    @abstractmethod
    async def streaming_asr(self, audio_data: bytes, **kwargs) -> AsyncIterator[Dict]:
        """流式语音识别"""
        pass

    @abstractmethod
    async def file_asr(self, audio_file: str, **kwargs) -> Dict:
        """文件语音识别"""
        pass

    @abstractmethod
    async def text_to_speech(self, text: str, **kwargs) -> bytes:
        """文字转语音"""
        pass


class VoiceServiceFactory:
    """语音服务工厂"""

    _services = {}

    @classmethod
    def register(cls, provider: str, service_class):
        """注册语音服务"""
        cls._services[provider] = service_class

    @classmethod
    def get_service(cls, provider: str, api_key: str, **kwargs):
        """获取语音服务实例"""
        if provider not in cls._services:
            # 如果厂商没有语音服务，使用豆包作为默认
            from base.plugins.llm.services.doubao_voice_service import DoubaoVoiceService
            logger.warning(f"{provider} 没有语音服务，使用豆包语音作为替代")
            return DoubaoVoiceService(api_key=api_key, **kwargs)

        service_class = cls._services[provider]
        return service_class(api_key=api_key, **kwargs)


# 导入各厂商语音服务
try:
    from base.plugins.llm.services.doubao_voice_service import DoubaoVoiceService
    VoiceServiceFactory.register("doubao", DoubaoVoiceService)
except ImportError:
    DoubaoVoiceService = None

# 应用官方demo的AST实现修复（Monkey Patch）
try:
    from base.plugins.llm.services.use_official_demo import streaming_translation_official
    if DoubaoVoiceService:
        DoubaoVoiceService.streaming_translation = streaming_translation_official
        logger.info("[AST] 已应用官方demo实现修复")
except ImportError as e:
    logger.warning(f"[AST] 无法应用官方demo修复: {e}")
except Exception as e:
    logger.warning(f"[AST] 应用官方demo修复时出错: {e}")


try:
    from base.plugins.llm.services.openai_voice_service import OpenAIVoiceService
    VoiceServiceFactory.register("openai", OpenAIVoiceService)
except ImportError:
    OpenAIVoiceService = None

try:
    from base.plugins.llm.services.baidu_voice_service import BaiduVoiceService
    VoiceServiceFactory.register("baidu", BaiduVoiceService)
except ImportError:
    BaiduVoiceService = None

try:
    from base.plugins.llm.services.alibaba_voice_service import AlibabaVoiceService
    VoiceServiceFactory.register("alibaba", AlibabaVoiceService)
except ImportError:
    AlibabaVoiceService = None

try:
    from base.plugins.llm.services.tencent_voice_service import TencentVoiceService
    VoiceServiceFactory.register("tencent", TencentVoiceService)
except ImportError:
    TencentVoiceService = None

# Anthropic、DeepSeek、智谱AI没有语音服务，将使用豆包作为默认
try:
    if DoubaoVoiceService:
        VoiceServiceFactory.register("anthropic", DoubaoVoiceService)
        VoiceServiceFactory.register("zhipu", DoubaoVoiceService)
        VoiceServiceFactory.register("deepseek", DoubaoVoiceService)
except:
    pass

__all__ = [
    "VoiceServiceBase",
    "VoiceServiceFactory"
]
