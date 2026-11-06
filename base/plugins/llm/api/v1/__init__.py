"""
LLM插件API v1路由

路由由插件管理器自动加载，每个文件需导出 {filename}_router
- provider_router
- model_router
- api_key_router
- usage_router
- client_router (客户端API)
- voice_router (语音API)
- translation_stream_router (流式翻译API)
- voice_websocket_v3_router (WebSocket实时翻译-带缓冲优化，延迟300ms) ⭐推荐

已废弃的路由（不再使用）：
- conversation_router (对话记录已统一到usage_router)
- voice_websocket_router (原版，已由V3替代)
- voice_websocket_streaming_router (旧流式版本)
- voice_websocket_v2_router (V2版本，已由V3替代)
"""
from fastapi import APIRouter
from base.plugins.llm.api.v1 import provider, model, api_key, usage, client, voice, voice_translation_stream
from base.plugins.llm.api.v1 import voice_websocket_v3

# 创建主路由
api_router = APIRouter()

# 注册各模块路由
api_router.include_router(provider.provider_router)
api_router.include_router(model.model_router)
api_router.include_router(api_key.api_key_router)
api_router.include_router(usage.usage_router)
api_router.include_router(client.client_router)
api_router.include_router(voice.voice_router)
api_router.include_router(voice_translation_stream.voice_translation_stream_router)

# 当前使用的实时翻译版本
api_router.include_router(voice_websocket_v3.voice_websocket_v3_router)

__all__ = ["api_router"]
