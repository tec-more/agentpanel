"""
客户端LLM API - 供客户端应用使用
只读接口：获取模型列表、发送聊天请求
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime
import json
import logging

from base.common.response import SuccessResponse
from base.common.security import get_current_user_id
from base.plugins.llm.models.provider import LLMProvider
from base.plugins.llm.models.model import LLMModel
from base.plugins.llm.models.api_key import LLMApiKey
from base.plugins.llm.schemas.llm import ChatRequest, Message, ChatResponse

logger = logging.getLogger(__name__)

client_router = APIRouter(
    prefix="/client",
    tags=["客户端LLM接口"],
    dependencies=[Depends(get_current_user_id)]  # 需要登录，但不限制权限
)


@client_router.get("/models", summary="获取可用模型列表（只读）")
async def get_available_models(
    status: str = Query("active", description="状态筛选"),
    current_user_id: int = Depends(get_current_user_id)
):
    """客户端获取可用的大模型列表"""
    query = LLMModel.filter(status=status).prefetch_related('provider')
    models = await query

    result = []
    for model in models:
        result.append({
            "id": model.id,
            "model_id": model.model_id,
            "model_name": model.model_name,
            "provider": {
                "id": model.provider.id,
                "name": model.provider.name,
                "name_en": model.provider.name_en,
                "logo_url": model.provider.logo_url
            },
            "context_length": model.context_length,
            "supports_streaming": model.supports_streaming,
            "supports_vision": model.supports_vision,
            "supports_function": model.supports_function,
            "description": model.description,
            "is_free": model.is_free
        })

    return SuccessResponse(data=result)


@client_router.get("/models/{model_id}", summary="获取模型详情（只读）")
async def get_model_detail(
    model_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """获取模型详细信息"""
    model = await LLMModel.get_or_none(id=model_id).prefetch_related('provider')
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    return SuccessResponse(data={
        "id": model.id,
        "model_id": model.model_id,
        "model_name": model.model_name,
        "provider": {
            "id": model.provider.id,
            "name": model.provider.name,
            "name_en": model.provider.name_en,
            "logo_url": model.provider.logo_url,
            "official_url": model.provider.official_url
        },
        "context_length": model.context_length,
        "input_price": float(model.input_price),
        "output_price": float(model.output_price),
        "supports_streaming": model.supports_streaming,
        "supports_vision": model.supports_vision,
        "supports_function": model.supports_function,
        "description": model.description,
        "is_free": model.is_free
    })


@client_router.get("/providers", summary="获取AI厂商列表（只读）")
async def get_providers(
    status: str = Query("active", description="状态筛选"),
    current_user_id: int = Depends(get_current_user_id)
):
    """获取AI厂商列表"""
    query = LLMProvider.filter(status=status)
    providers = await query

    result = []
    for provider in providers:
        result.append({
            "id": provider.id,
            "name": provider.name,
            "name_en": provider.name_en,
            "logo_url": provider.logo_url,
            "official_url": provider.official_url,
            "description": provider.description
        })

    return SuccessResponse(data=result)


@client_router.post("/chat", summary="发送聊天请求")
async def create_chat(
    data: ChatRequest,
    current_user_id: int = Depends(get_current_user_id)
):
    """
    发送聊天请求

    客户端使用流程：
    1. 创建对话或继续已有对话
    2. 发送消息
    3. 返回助手回复
    """
    from base.plugins.llm.services.chat_service import ChatService

    try:
        # 1. 获取模型信息
        model = await LLMModel.get_or_none(id=data.model).prefetch_related('provider')
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        if model.status != "active":
            raise HTTPException(status_code=400, detail="模型未启用")

        # 2. 获取可用的API密钥
        api_key_obj = await LLMApiKey.filter(
            model_id=model.model_id
        ).first()
        if not api_key_obj:
            raise HTTPException(status_code=503, detail="没有可用的API密钥")

        # 3. 获取厂商服务实例
        endpoint_url = model.endpoint_url or api_key_obj.endpoint_url or model.provider.official_url
        if endpoint_url:
            endpoint_url = endpoint_url.rstrip('/')
            if endpoint_url.endswith('/chat/completions'):
                endpoint_url = endpoint_url[:-len('/chat/completions')]
            # 移除错误的 /responses 路径
            if '/responses' in endpoint_url:
                endpoint_url = endpoint_url.split('/responses')[0]
        
        credentials = api_key_obj.get_credentials()
        service = await ChatService.get_provider_service(
            provider_name_en=model.provider.name_en,
            api_key=credentials.get("api_key", ""),
            endpoint_url=endpoint_url,
            api_secret=credentials.get("api_secret", ""),
            call_mode=credentials.get("call_mode", "vendor_sdk"),
        )

        # 4. 如果是流式请求
        if data.stream:
            return StreamingResponse(
                chat_stream_internal(
                    service=service,
                    model=model.model_id,
                    messages=data.messages,
                    temperature=data.temperature,
                    max_tokens=data.max_tokens,
                    top_p=data.top_p,
                    user_id=current_user_id
                ),
                media_type="text/event-stream"
            )

        # 5. 非流式请求
        result = await service.chat(
            model=model.model_id,
            messages=[{"role": m.role, "content": m.content} for m in data.messages],
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            top_p=data.top_p,
            stream=False
        )

        # 6. 解析响应
        assistant_message = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        # 7. 计算费用
        cost = await ChatService.calculate_cost(
            model.id,
            prompt_tokens,
            completion_tokens
        )

        # 8. 创建对话记录
        conversation = await ChatService.create_conversation(
            customer_id=current_user_id,
            model_id=model.id,
            messages=[{"role": m.role, "content": m.content} for m in data.messages]
        )

        # 9. 更新对话记录
        await ChatService.update_conversation(
            conversation=conversation,
            assistant_message=assistant_message,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost=cost
        )

        # 10. 更新API密钥使用量
        await ChatService.update_api_key_usage(api_key_obj, total_tokens)

        return SuccessResponse(data={
            "conversation_id": conversation.conversation_id,
            "message": assistant_message,
            "model": model.model_id,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"聊天请求失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"聊天请求失败: {str(e)}")


async def chat_stream_internal(
    service,
    model: str,
    messages: List[Message],
    temperature: float,
    max_tokens: int,
    top_p: float,
    user_id: int
):
    """
    内部流式聊天生成器

    Args:
        service: 厂商服务实例
        model: 模型ID
        messages: 消息列表
        temperature: 温度
        max_tokens: 最大tokens
        top_p: 采样参数
        user_id: 用户ID

    Yields:
        SSE格式数据
    """
    from base.plugins.llm.services.chat_service import ChatService

    full_response = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        # 调用流式API
        async for chunk in service.chat_stream(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p
        ):
            # 提取内容
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "")
            finish_reason = chunk["choices"][0].get("finish_reason")

            if content:
                full_response += content

            # 获取usage（通常在最后一个chunk中）
            if "usage" in chunk:
                usage = chunk["usage"]
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

            # 发送SSE数据
            sse_data = {
                "id": chunk.get("id", ""),
                "choices": chunk["choices"],
                "model": chunk.get("model", model)
            }
            yield f"data: {json.dumps(sse_data)}\n\n"

            if finish_reason:
                break

        # 发送结束标记
        yield "data: [DONE]\n\n"

        # 保存对话记录（异步，不阻塞流）
        # TODO: 考虑使用后台任务保存
        try:
            model_obj = await LLMModel.get_or_none(model_id=model)
            if model_obj:
                cost = await ChatService.calculate_cost(
                    model_obj.id,
                    prompt_tokens,
                    completion_tokens
                )

                conversation = await ChatService.create_conversation(
                    customer_id=user_id,
                    model_id=model_obj.id,
                    messages=[{"role": m.role, "content": m.content} for m in messages]
                )

                await ChatService.update_conversation(
                    conversation=conversation,
                    assistant_message=full_response,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_cost=cost
                )

        except Exception as e:
            logger.error(f"保存对话记录失败: {str(e)}")

    except Exception as e:
        logger.error(f"流式聊天失败: {str(e)}", exc_info=True)
        error_data = {"error": {"message": str(e), "type": "chat_error"}}
        yield f"data: {json.dumps(error_data)}\n\n"
