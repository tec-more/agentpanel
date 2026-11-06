"""
语音服务辅助工具 - 自动获取语音专用API Key
"""
from typing import Dict, Optional
from fastapi import HTTPException
import logging

from base.plugins.llm.models.api_key import LLMApiKey
from base.plugins.llm.models.provider import LLMProvider
from base.plugins.llm.models.enums import ModelServiceType
from base.plugins.llm.services.voice_service_base import VoiceServiceFactory

logger = logging.getLogger(__name__)


class VoiceServiceHelper:
    """语音服务辅助类"""

    @staticmethod
    async def get_voice_api_key(provider_id: int, service_type: str = None) -> LLMApiKey:
        """
        获取可用的语音API密钥

        优先使用语音专用密钥，支持按服务类型筛选

        Args:
            provider_id: 厂商ID
            service_type: 服务类型（可选），如 "streaming_asr", "tts" 等

        Returns:
            API密钥对象
        """
        # 构建查询条件
        query = LLMApiKey.filter(
            provider_id=provider_id,
            status="active"
        )

        # 如果指定了服务类型，按类型筛选
        if service_type:
            query = query.filter(model_service_type=service_type)
            logger.info(f"按服务类型筛选: {service_type}")
        else:
            # 否则筛选所有语音服务类型
            voice_types = [t.value for t in ModelServiceType.voice_services()]
            query = query.filter(model_service_type__in=voice_types)

        # 获取该厂商下所有可用的API密钥
        api_keys = await query.all()

        # 过滤出真正可用的
        available_keys = []
        for key in api_keys:
            if key.is_available:
                available_keys.append(key)

        if not available_keys:
            # 如果没有找到语音服务专用密钥，回退到LLM密钥
            logger.warning(
                f"厂商ID {provider_id} 未配置{service_type or '语音'}专用密钥，回退到LLM密钥"
            )
            available_keys = await LLMApiKey.filter(
                provider_id=provider_id,
                status="active",
                model_service_type=ModelServiceType.LLM.value
            ).all()
            available_keys = [k for k in available_keys if k.is_available]

            if not available_keys:
                raise HTTPException(
                    status_code=503,
                    detail=f"厂商ID {provider_id} 没有可用的API密钥"
                )

        # 使用已使用配额最少的密钥
        available_keys.sort(key=lambda k: k.used_quota)
        selected_key = available_keys[0]

        logger.info(
            f"使用API密钥: {selected_key.api_id or selected_key.model_service_type} "
            f"(类型: {selected_key.model_service_type})"
        )
        return selected_key

    @staticmethod
    async def get_voice_service(
        provider_id: int,
        service_type: str = None,
        provider_name_en: Optional[str] = None
    ):
        """
        获取语音服务实例，自动使用正确的API密钥

        Args:
            provider_id: 厂商ID
            service_type: 服务类型（如 "streaming_asr", "tts" 等）
            provider_name_en: 厂商英文标识（可选，如果提供会更高效）

        Returns:
            语音服务实例（已初始化API密钥）
        """
        # 获取API密钥
        api_key_obj = await VoiceServiceHelper.get_voice_api_key(provider_id, service_type)

        # 获取凭据（使用新的统一方法）
        credentials = api_key_obj.get_credentials()

        # 获取厂商英文名
        if not provider_name_en:
            provider = await LLMProvider.get(id=provider_id)
            provider_name_en = provider.name_en

        # 创建语音服务实例
        service = VoiceServiceFactory.get_service(
            provider=provider_name_en,
            api_key=credentials["api_key"],
            endpoint_url=credentials["endpoint_url"],
            api_secret=credentials.get("api_secret"),
            api_id=credentials.get("api_id"),
            access_token=credentials.get("access_token")
        )

        # 保存API密钥对象引用，方便后续更新使用量
        service._api_key_obj = api_key_obj

        return service

    @staticmethod
    async def update_voice_usage(
        service,
        tokens: int = 0,
        duration_seconds: int = 0
    ):
        """
        更新语音服务使用量

        Args:
            service: 语音服务实例
            tokens: token数量
            duration_seconds: 音频时长（秒）
        """
        if hasattr(service, '_api_key_obj'):
            api_key_obj = service._api_key_obj

            # 更新使用量（token或时长，取较大值）
            from datetime import datetime
            usage = max(tokens, duration_seconds)
            api_key_obj.used_quota += usage
            api_key_obj.last_used_at = datetime.now()
            await api_key_obj.save()

            logger.info(
                f"更新语音服务使用量: {api_key_obj.api_id or api_key_obj.model_service_type} "
                f"+{usage} (总计: {api_key_obj.used_quota})"
            )
