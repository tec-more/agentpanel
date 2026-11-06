"""
使用记录追踪器
用于记录客户对 AI 服务和 API 的调用情况
"""
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

from base.plugins.llm.models.usage import LLMUsageRecord


class UsageTracker:
    """使用记录追踪器"""

    @staticmethod
    async def log_usage(
        customer_id: int,
        service_type: str,
        duration_seconds: int,
        api_cost: float,
        details: Dict[str, Any],
        characters_count: int = 0,
        session_id: Optional[str] = None
    ) -> LLMUsageRecord:
        """
        记录服务使用情况

        Args:
            customer_id: 客户ID
            service_type: 服务类型（text_generation/image_generation/tts 等）
            duration_seconds: 使用时长（秒）
            api_cost: API 成本
            details: 详细信息（JSON 格式）
            characters_count: 字符数（可选）
            session_id: 会话ID（可选，自动生成）

        Returns:
            创建的使用记录对象
        """
        # 生成会话ID（如果未提供）
        if not session_id:
            session_id = str(uuid.uuid4())[:32]

        # 映射服务类型到记录类型
        record_type_map = {
            'text_generation': 'conversation',
            'translation': 'voice',
            'tts': 'tts',
            'voice_clone': 'voice_clone'
        }
        record_type = record_type_map.get(service_type, 'conversation')

        # 创建使用记录
        log = await LLMUsageRecord.create(
            record_id=session_id,
            customer_id=customer_id,
            model_id=details.get('model_id', 1),  # 默认模型ID
            record_type=record_type,
            status='completed',
            tokens=details.get('total_tokens', 0),
            cost=Decimal(str(api_cost)),
            input_text=details.get('input_text', ''),
            output_text=details.get('output_text', ''),
            extra_info=details
        )

        print(f"[UsageTracker] 记录使用: customer={customer_id}, type={service_type}, cost=${api_cost}")

        return log

    @staticmethod
    async def log_openai_usage(
        customer_id: int,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_seconds: int,
        details: Optional[Dict[str, Any]] = None
    ) -> LLMUsageRecord:
        """
        记录 OpenAI API 使用（便捷方法）

        Args:
            customer_id: 客户ID
            model: 模型名称（如 gpt-4, claude-3-opus）
            prompt_tokens: 提示 Token 数
            completion_tokens: 完成 Token 数
            duration_seconds: 请求时长
            details: 额外详细信息

        Returns:
            使用记录对象
        """
        # 计算成本（示例价格，需根据实际情况调整）
        price_per_1k_tokens = {
            "gpt-4": 0.03,
            "gpt-4-turbo": 0.01,
            "gpt-3.5-turbo": 0.001,
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003,
        }

        total_tokens = prompt_tokens + completion_tokens
        cost = (total_tokens / 1000) * price_per_1k_tokens.get(model, 0.001)

        # 构建详细信息
        log_details = details or {}
        log_details.update({
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens
        })

        return await UsageTracker.log_usage(
            customer_id=customer_id,
            service_type="text_generation",
            duration_seconds=duration_seconds,
            api_cost=cost,
            details=log_details,
            characters_count=total_tokens * 4  # 粗略估计：1 token ≈ 4 字符
        )

    @staticmethod
    async def log_image_generation(
        customer_id: int,
        model: str,
        image_size: str,
        prompt: str,
        duration_seconds: int,
        cost: float
    ) -> LLMUsageRecord:
        """
        记录图像生成使用（便捷方法）

        Args:
            customer_id: 客户ID
            model: 模型名称（dall-e-3, stable-diffusion 等）
            image_size: 图像尺寸
            prompt: 提示词
            duration_seconds: 生成时长
            cost: 成本

        Returns:
            使用记录对象
        """
        return await UsageTracker.log_usage(
            customer_id=customer_id,
            service_type="image_generation",
            duration_seconds=duration_seconds,
            api_cost=cost,
            details={
                "model": model,
                "image_size": image_size,
                "prompt": prompt[:200]  # 保存前200字符
            }
        )

    @staticmethod
    async def log_tts_usage(
        customer_id: int,
        model: str,
        text_length: int,
        duration_seconds: int,
        cost: float,
        voice: str = "alloy"
    ) -> LLMUsageRecord:
        """
        记录语音合成使用（便捷方法）

        Args:
            customer_id: 客户ID
            model: TTS 模型
            text_length: 文本长度
            duration_seconds: 音频时长
            cost: 成本
            voice: 音色

        Returns:
            使用记录对象
        """
        return await UsageTracker.log_usage(
            customer_id=customer_id,
            service_type="tts",
            duration_seconds=duration_seconds,
            api_cost=cost,
            details={
                "model": model,
                "voice": voice,
                "text_length": text_length
            },
            characters_count=text_length
        )
