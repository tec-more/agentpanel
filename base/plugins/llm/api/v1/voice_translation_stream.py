"""
豆包AST 2.0 实时同声传译API - 流式响应版本
支持Server-Sent Events (SSE)实现真正的实时翻译
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import AsyncIterator
import logging
import json
import asyncio

from base.common.response import SuccessResponse
from base.common.security import get_current_user_id
from base.plugins.llm.models.usage import LLMUsageRecord
from base.plugins.llm.services.voice_helper import VoiceServiceHelper

logger = logging.getLogger(__name__)

voice_translation_stream_router = APIRouter(
    prefix="/voice/translation",
    tags=["语音翻译-流式"],
)

# 别名，用于向后兼容
translation_stream_router = voice_translation_stream_router


@voice_translation_stream_router.post("/streaming", summary="实时同声传译（流式SSE）")
async def streaming_translation_sse(
    audio_file: UploadFile,
    provider_id: int = Form(..., description="厂商ID"),
    source_language: str = Form("zh", description="源语言"),
    target_language: str = Form("en", description="目标语言"),
    format: str = Form("wav", description="音频格式"),
    sample_rate: int = Form(16000, description="采样率"),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    实时同声传译 - 使用Server-Sent Events (SSE)

    返回流式翻译结果，客户端可以实时接收：
    - 原文识别结果
    - 翻译结果
    - TTS音频数据（可选）

    事件类型：
    - source_subtitle: 原文字幕
    - translation_subtitle: 翻译字幕
    - tts_audio: 合成音频
    - session_finished: 会话完成
    - error: 错误信息

    使用示例：
    ```
    const response = await fetch('/api/v1/llm/voice/translation/streaming', {
        method: 'POST',
        body: formData,
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        const lines = text.split('\\n\\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                console.log('Event:', data.event, data);
            }
        }
    }
    ```
    """

    async def event_generator() -> AsyncIterator[str]:
        """生成SSE事件流"""
        record = None
        try:
            # 获取语音服务
            service = await VoiceServiceHelper.get_voice_service(
                provider_id,
                service_type="translation"
            )

            # 读取音频数据
            raw_audio_data = await audio_file.read()

            # 关键修复：提取纯PCM数据（不包含WAV头）
            # 豆包AST需要纯PCM数据，不是完整的WAV文件
            import wave
            import io

            try:
                audio_file_obj = io.BytesIO(raw_audio_data)
                with wave.open(audio_file_obj, 'rb') as wf:
                    # 读取纯PCM数据（不包含WAV头）
                    audio_data = wf.readframes(wf.getnframes())
                    logger.info(f"[SSE流] 提取PCM数据: {len(audio_data)} bytes (原始WAV: {len(raw_audio_data)} bytes)")
            except Exception as e:
                logger.warning(f"[SSE流] 无法提取PCM数据: {e}，使用原始数据")
                audio_data = raw_audio_data

            # 创建记录（使用UUID避免重复）
            import uuid
            record_id = f"trans_{uuid.uuid4().hex[:16]}"
            record = await LLMUsageRecord.create(
                record_id=record_id,
                customer_id=current_user_id,
                model_id=provider_id,
                record_type="voice",
                audio_file=audio_file.filename,
                audio_format=format,
                source_language=source_language,
                target_language=target_language,
                status="processing"
            )

            # 发送开始事件
            yield f"event: start\ndata: {json.dumps({'session_id': record_id})}\n\n"

            # 调用流式翻译服务
            final_result = None
            event_count = 0

            async for result in service.streaming_translation(
                audio_data, source_language, target_language, format, sample_rate
            ):
                event_count += 1
                result['sequence'] = event_count

                # 发送SSE格式的数据
                event_type = result.get("event", "unknown")
                yield f"event: {event_type}\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"

                # 保存最终结果
                if event_type == "session_finished":
                    final_result = result.get("result", {})

            # 更新记录
            if final_result and record:
                from datetime import datetime
                import pytz
                end_time = datetime.now(pytz.UTC)
                duration_seconds = 0
                if record.start_time:
                    duration_seconds = int((end_time - record.start_time).total_seconds())
                
                await LLMUsageRecord.filter(id=record.id).update(
                    input_text=final_result.get("source_text", ""),
                    output_text=final_result.get("translation_text", ""),
                    audio_duration=duration_seconds,
                    status="completed",
                    end_time=end_time
                )

                # 更新使用量
                tokens = final_result.get("tokens", {})
                total_tokens = sum(tokens.values()) if tokens else 0
                if total_tokens > 0:
                    await VoiceServiceHelper.update_voice_usage(
                        service,
                        tokens=int(total_tokens)
                    )

            # 发送完成事件
            yield f"event: complete\ndata: {json.dumps({'record_id': record_id, 'total_events': event_count})}\n\n"

        except Exception as e:
            logger.error(f"[翻译流] 处理失败: {str(e)}", exc_info=True)

            # 更新记录状态为失败
            if record:
                try:
                    from datetime import datetime
                    import pytz
                    end_time = datetime.now(pytz.UTC)
                    duration_seconds = 0
                    if record.start_time:
                        duration_seconds = int((end_time - record.start_time).total_seconds())
                    
                    await LLMUsageRecord.filter(id=record.id).update(
                        audio_duration=duration_seconds,
                        status="failed",
                        end_time=end_time
                    )
                except:
                    pass

            # 发送错误事件
            error_data = {
                'error': str(e),
                'type': type(e).__name__
            }
            yield f"event: error\ndata: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        }
    )


@voice_translation_stream_router.post("/streaming/chunked", summary="实时同声传译（分块上传）")
async def streaming_translation_chunked(
    provider_id: int = Form(..., description="厂商ID"),
    source_language: str = Form("zh", description="源语言"),
    target_language: str = Form("en", description="目标语言"),
    format: str = Form("wav", description="音频格式"),
    sample_rate: int = Form(16000, description="采样率"),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    实时同声传译 - 支持分块上传音频

    适用于实时录音场景，可以边录音边上传
    """

    async def event_generator() -> AsyncIterator[str]:
        """生成SSE事件流"""
        try:
            # 获取语音服务
            service = await VoiceServiceHelper.get_voice_service(
                provider_id,
                service_type="translation"
            )

            # TODO: 实现WebSocket双向通信
            # 客户端通过WebSocket发送音频块
            # 服务端返回实时翻译结果

            yield f"event: info\ndata: {json.dumps({'message': 'WebSocket模式待实现'})}\n\n"

        except Exception as e:
            logger.error(f"[翻译流] 处理失败: {str(e)}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# 导出路由
__all__ = ["voice_translation_stream_router"]
