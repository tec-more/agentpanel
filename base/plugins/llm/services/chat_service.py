"""
大模型聊天服务 - 统一调用入口
"""
from typing import Optional, List, Dict, AsyncIterator
import logging
from fastapi import HTTPException
from openai import api_key

from base.plugins.llm.models.model import LLMModel
from base.plugins.llm.models.api_key import LLMApiKey
# 从统一的使用记录表导入
from base.plugins.llm.models.usage import LLMUsageRecord
from base.plugins.llm.models.provider import LLMProvider

logger = logging.getLogger(__name__)


# 导入各厂商服务
try:
    from base.plugins.llm.services.doubao_service import DoubaoService
except ImportError:
    DoubaoService = None

try:
    from base.plugins.llm.services.openai_service import OpenAIService
except ImportError:
    OpenAIService = None

try:
    from base.plugins.llm.services.localai_service import LocalAIService
except ImportError:
    LocalAIService = None

try:
    from base.plugins.llm.services.anthropic_service import AnthropicService
except ImportError:
    AnthropicService = None

try:
    from base.plugins.llm.services.alibaba_service import AlibabaService
except ImportError:
    AlibabaService = None

try:
    from base.plugins.llm.services.zhipu_service import ZhipuService
except ImportError:
    ZhipuService = None

try:
    from base.plugins.llm.services.deepseek_service import DeepSeekService
except ImportError:
    DeepSeekService = None

try:
    from base.plugins.llm.services.tencent_service import TencentService
except ImportError:
    TencentService = None

try:
    from base.plugins.llm.services.baidu_service import BaiduService
except ImportError:
    BaiduService = None


class ChatService:
    """聊天服务统一管理类"""

    @staticmethod
    async def get_available_api_key(provider_id: int) -> Optional[LLMApiKey]:
        """
        获取可用的API密钥（轮询策略）

        Args:
            provider_id: 厂商ID

        Returns:
            可用的API密钥对象
        """
        # 获取该厂商下所有可用的API密钥
        api_keys = await LLMApiKey.filter(
            provider_id=provider_id,
            status="active"
        ).all()

        # 过滤出真正可用的（配额未超、未过期等）
        available_keys = []
        for key in api_keys:
            if key.is_available:
                available_keys.append(key)

        if not available_keys:
            raise HTTPException(status_code=503, detail="没有可用的API密钥")

        # 简单轮询：选择已使用配额最少的密钥
        available_keys.sort(key=lambda k: k.used_quota)
        return available_keys[0]

    @staticmethod
    async def get_provider_service(provider_name_en: str, api_key: str, endpoint_url: str, api_secret: str = None, call_mode: str = "vendor_sdk"):
        """
        根据厂商获取对应的服务实例

        Args:
            provider_name_en: 厂商英文标识
            api_key: API密钥对象
            endpoint_url: API端点
            api_secret: API密钥（部分厂商需要）
            call_mode: 调用方式，openapi或vendor_sdk

        Returns:
            厂商服务实例
        """
        # 如果是OpenAPI模式，直接使用OpenAIService
        if call_mode == "openapi":
            if not OpenAIService:
                raise HTTPException(status_code=500, detail="OpenAPI服务未配置")
            return OpenAIService(api_key=api_key, endpoint_url=endpoint_url)

        # 否则使用厂商SDK模式
        if provider_name_en == "doubao":
            if not DoubaoService:
                raise HTTPException(status_code=500, detail="豆包服务未配置")
            return DoubaoService(api_key=api_key, endpoint_url=endpoint_url)

        elif provider_name_en == "openai":
            if not OpenAIService:
                raise HTTPException(status_code=500, detail="OpenAI服务未配置")
            return OpenAIService(api_key=api_key, endpoint_url=endpoint_url)
        
        elif provider_name_en == "local":
            if not OpenAIService:
                raise HTTPException(status_code=500, detail="OpenAI服务未配置")
            return OpenAIService(api_key=api_key, endpoint_url=endpoint_url)

        elif provider_name_en == "anthropic":
            if not AnthropicService:
                raise HTTPException(status_code=500, detail="Anthropic服务未配置")
            return AnthropicService(api_key=api_key, endpoint_url=endpoint_url)

        elif provider_name_en == "alibaba":
            if not AlibabaService:
                raise HTTPException(status_code=500, detail="阿里云服务未配置")
            return AlibabaService(api_key=api_key, endpoint_url=endpoint_url)

        elif provider_name_en == "zhipu":
            if not ZhipuService:
                raise HTTPException(status_code=500, detail="智谱AI服务未配置")
            return ZhipuService(api_key=api_key, endpoint_url=endpoint_url)

        elif provider_name_en == "deepseek":
            if not DeepSeekService:
                raise HTTPException(status_code=500, detail="DeepSeek服务未配置")
            return DeepSeekService(api_key=api_key, endpoint_url=endpoint_url)

        elif provider_name_en == "tencent":
            if not TencentService:
                raise HTTPException(status_code=500, detail="腾讯服务未配置")
            return TencentService(api_key=api_key, api_secret=api_secret, endpoint_url=endpoint_url)

        elif provider_name_en == "baidu":
            if not BaiduService:
                raise HTTPException(status_code=500, detail="百度服务未配置")
            if not api_secret:
                raise HTTPException(status_code=400, detail="百度服务需要API Secret")
            return BaiduService(api_key=api_key, api_secret=api_secret, endpoint_url=endpoint_url)

        raise HTTPException(status_code=400, detail=f"不支持的厂商: {provider_name_en}")

    @staticmethod
    async def create_conversation(
        customer_id: int,
        model_id: int,
        messages: List[Dict]
    ) -> LLMUsageRecord:
        """
        创建新对话记录

        Args:
            customer_id: 客户ID
            model_id: 模型ID
            messages: 初始消息列表

        Returns:
            对话对象
        """
        import uuid
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        # 简单估算token数（使用豆包的估算方法作为通用方法）
        total_tokens = 0
        for msg in messages:
            content = msg.get("content", "")
            chinese_chars = len([c for c in content if '\u4e00' <= c <= '\u9fff'])
            english_chars = len(content) - chinese_chars
            total_tokens += int(chinese_chars / 1.5 + english_chars / 4)

        from datetime import datetime
        import pytz
        conversation = await LLMUsageRecord.create(
            record_id=conversation_id,
            conversation_id=conversation_id,
            customer_id=customer_id,
            model_id=model_id,
            record_type="conversation",
            input_text=messages[0].get("content", ""),
            tokens=total_tokens,
            status="active",
            start_time=datetime.now(pytz.UTC)
        )

        return conversation

    @staticmethod
    async def update_conversation(
        conversation: LLMUsageRecord,
        assistant_message: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost: float
    ):
        """
        更新对话记录

        Args:
            conversation: 对话对象
            assistant_message: 助手回复消息
            prompt_tokens: 输入token数
            completion_tokens: 输出token数
            total_cost: 总费用
        """
        # 更新统计
        conversation.output_text = assistant_message
        conversation.tokens += (prompt_tokens + completion_tokens)
        conversation.cost += total_cost
        await conversation.save()

        # 不再需要创建额外的使用记录，因为我们已经使用统一的表

    @staticmethod
    async def calculate_cost(model_id: int, prompt_tokens: int, completion_tokens: int) -> float:
        """
        计算费用

        Args:
            model_id: 模型ID
            prompt_tokens: 输入token数
            completion_tokens: 输出token数

        Returns:
            费用（元）
        """
        model = await LLMModel.get_or_none(id=model_id)
        if not model:
            return 0.0

        # 费用 = 输入token * 输入单价 + 输出token * 输出单价
        # 价格单位是元/1K tokens
        input_cost = (prompt_tokens / 1000) * float(model.input_price)
        output_cost = (completion_tokens / 1000) * float(model.output_price)

        return input_cost + output_cost

    @staticmethod
    async def update_api_key_usage(api_key: LLMApiKey, tokens: int):
        """
        更新API密钥使用量

        Args:
            api_key: API密钥对象
            tokens: 本次使用的token数
        """
        from datetime import datetime
        api_key.used_quota += tokens
        api_key.last_used_at = datetime.now()
        await api_key.save()

    @staticmethod
    async def chat_stream(
        model_id: int,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream_callback=None
    ) -> AsyncIterator[str]:
        """
        流式聊天（支持边思考边输出）

        Args:
            model_id: 模型ID
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            stream_callback: 流式回调函数，用于实时推送内容

        Yields:
            流式内容片段
        """
        from base.plugins.llm.services.openai_service import OpenAIService
        
        logger.info(f"[ChatService] 开始流式聊天, model_id={model_id}")
        
        # 获取模型信息
        target_model = await LLMModel.get_or_none(id=model_id, status="active")
        if not target_model:
            raise HTTPException(status_code=404, detail=f"未找到model_id={model_id}的活跃模型")
        logger.info(f"[ChatService] 开始流式聊天，模型标识, id={target_model.id}, model_id={target_model.model_id}")
        # 获取厂商
        provider = await LLMProvider.get_or_none(id=target_model.provider_id)
        if not provider:
            logger.error(f"[ChatService] 未找到对应的厂商, model_id={model_id}")
            raise HTTPException(status_code=404, detail=f"未找到对应的厂商")
        
        # 获取API密钥 - 先尝试根据模型查找，再尝试根据厂商查找
        api_key_obj = None
        
        # 1. 先尝试根据模型查找（优先级更高）
        try:
            from base.plugins.llm.models.api_key import LLMApiKey
            api_key_obj = await LLMApiKey.filter(
                model_id=target_model.id
            ).first()
            
            logger.info(f"[ChatService] 找到模型专用API密钥: {api_key_obj.api_id or api_key_obj.description}")
        except Exception as e:
            logger.warning(f"[ChatService] 根据模型查找API密钥失败: {e}")
    
    
        api_key_str = api_key_obj.api_key
        api_secret = getattr(api_key_obj, 'api_secret', None)
        
        # 优先使用API密钥的call_mode，否则使用模型的call_mode
        call_mode = api_key_obj.call_mode or target_model.call_mode or "vendor_sdk"
              
        # 构建端点URL - 优先使用API密钥的endpoint，其次使用模型的endpoint，最后使用默认值
        endpoint_url = api_key_obj.endpoint_url or target_model.endpoint_url or "https://api.openai.com/v1"
        # 清理端点 URL，移除错误的路径
        if endpoint_url:
            endpoint_url = endpoint_url.rstrip('/')
            # 移除错误的 /responses 路径
            if '/responses' in endpoint_url:
                endpoint_url = endpoint_url.split('/responses')[0]
            # 移除末尾的 /chat/completions
            if endpoint_url.endswith('/chat/completions'):
                endpoint_url = endpoint_url[:-len('/chat/completions')]
        
        service = await ChatService.get_provider_service(
            provider.name_en,
            api_key_str,
            endpoint_url,
            api_secret,
            call_mode,
        )
        
        # 调用流式chat - 优先使用model_id（API标识），否则使用model_name
        model_for_call = target_model.model_id if target_model.model_id else target_model.model_name
        
        if hasattr(service, 'chat_stream'):
            async for chunk in service.chat_stream(
                model=model_for_call,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                logger.info(f"[ChatService] 收到chunk: {chunk}")
                # 提取content
                if 'choices' in chunk and len(chunk['choices']) > 0:
                    delta = chunk['choices'][0].get('delta', {})
                    content = delta.get('content', '')
                    logger.info(f"[ChatService] 提取content: {content}")
                    if content:
                        # 如果有回调，立即调用
                        if stream_callback:
                            logger.info(f"[ChatService] 调用回调推送content: {content}")
                            await stream_callback(content)
                        yield content
        else:
            # 如果服务不支持流式，回退到非流式
            logger.warning(f"[ChatService] {provider.name_en}服务不支持流式，回退到非流式")
            response = await service.chat(
                model=model_for_call,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            if stream_callback:
                await stream_callback(content)
            yield content
