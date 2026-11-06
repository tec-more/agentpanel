"""
LLM插件服务模块

提供各大厂商的大模型调用服务
"""
from base.plugins.llm.services.chat_service import ChatService
from base.plugins.llm.services.doubao_service import DoubaoService
from base.plugins.llm.services.openai_service import OpenAIService
from base.plugins.llm.services.localai_service import LocalAIService
from base.plugins.llm.services.baidu_service import BaiduService
from base.plugins.llm.services.anthropic_service import AnthropicService
from base.plugins.llm.services.alibaba_service import AlibabaService
from base.plugins.llm.services.zhipu_service import ZhipuService
from base.plugins.llm.services.deepseek_service import DeepSeekService
from base.plugins.llm.services.tencent_service import TencentService
from base.plugins.llm.services.baidu_service import BaiduService

__all__ = [
    "ChatService",
    "DoubaoService",
    "OpenAIService",
    "AnthropicService",
    "AlibabaService",
    "ZhipuService",
    "DeepSeekService",
    "LocalAIService",
    "TencentService",
    "BaiduService"
]
