"""
模型服务类型枚举定义
"""
from enum import Enum


class CallMode(str, Enum):
    """大模型调用方式枚举

    用于标识API Key使用哪种方式调用大模型
    """
    OPENAPI = "openapi"  # OpenAPI 格式，使用 openai 库
    VENDOR_SDK = "vendor_sdk"  # 厂商SDK模式，使用厂商提供的SDK

    @classmethod
    def display_name(cls, value: str) -> str:
        """获取调用方式的显示名称"""
        names = {
            cls.OPENAPI.value: "OpenAPI 格式",
            cls.VENDOR_SDK.value: "厂商 SDK 模式",
        }
        return names.get(value, value)


class ModelServiceType(str, Enum):
    """模型服务类型枚举

    用于标识API Key的具体用途，支持大语言模型和各种语音服务
    """
    LLM = "llm"                      # 大语言模型
    EMBEDDING = "embedding"          # 向量模型
    STREAMING_ASR = "streaming_asr"  # 流式语音识别（实时）
    FILE_ASR = "file_asr"            # 录音文件识别
    TTS = "tts"                      # 语音合成
    VOICE_CLONE = "voice_clone"      # 声音复刻
    P2P_VOICE = "p2p_voice"          # P2P实时语音
    TRANSLATION = "translation"      # 同声传译

    @classmethod
    def voice_services(cls) -> list:
        """获取所有语音服务类型"""
        return [
            cls.STREAMING_ASR,
            cls.FILE_ASR,
            cls.TTS,
            cls.VOICE_CLONE,
            cls.P2P_VOICE,
            cls.TRANSLATION,
        ]

    @classmethod
    def display_name(cls, value: str) -> str:
        """获取服务类型的显示名称"""
        names = {
            cls.LLM.value: "大语言模型",
            cls.EMBEDDING.value: "向量模型",
            cls.STREAMING_ASR.value: "流式语音识别",
            cls.FILE_ASR.value: "录音文件识别",
            cls.TTS.value: "语音合成",
            cls.VOICE_CLONE.value: "声音复刻",
            cls.P2P_VOICE.value: "P2P实时语音",
            cls.TRANSLATION.value: "同声传译",
        }
        return names.get(value, value)

    def is_voice_service(self) -> bool:
        """判断当前类型是否为语音服务"""
        return self.value in [t.value for t in self.voice_services()]


__all__ = ['ModelServiceType', 'CallMode']
