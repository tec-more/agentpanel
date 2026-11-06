"""
实时语音翻译 - WebSocket双向通信
支持客户端边录音边发送，服务器实时接收并翻译
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging
import json
import uuid
import io
import wave
from pathlib import Path

from base.common.security import get_current_user_id_ws
from base.plugins.llm.models.usage import LLMUsageRecord
from base.plugins.llm.services.voice_helper import VoiceServiceHelper

logger = logging.getLogger(__name__)

voice_websocket_router = APIRouter(
    prefix="/voice",
    tags=["语音服务-WebSocket"],
)

# 别名，用于向后兼容
websocket_router = voice_websocket_router


@voice_websocket_router.websocket("/translation/streaming")
async def websocket_translation(
    websocket: WebSocket,
    provider_id: int = Query(..., description="厂商ID"),
    token: Optional[str] = Query(None, description="认证token")
):
    """
    实时语音翻译 - WebSocket接口

    协议：
    1. 客户端连接后，发送开始消息
    2. 客户端持续发送音频块（二进制）
    3. 服务器缓存音频，检测到结束后调用豆包AST
    4. 服务器返回翻译结果（JSON）

    客户端消息格式：
    - 控制消息（JSON）：
      {"type": "start", "format": "wav", "sample_rate": 16000, "source_language": "zh", "target_language": "en"}
      {"type": "end"}

    - 音频数据（二进制）：原始音频块

    服务器响应格式（JSON）：
      {"type": "started", "session_id": "xxx"}
      {"type": "progress", "received_bytes": 12345, "chunks": 10}
      {"type": "processing", "audio_size": 12345}
      {"type": "result", "source_text": "原文", "translation_text": "译文", "record_id": "xxx"}
      {"type": "error", "message": "错误信息"}

    使用示例（JavaScript）：
    ```javascript
    const ws = new WebSocket('ws://localhost:9998/v1/llm/voice/translation/streaming?provider_id=1&token=xxx');

    // 发送开始消息
    ws.send(JSON.stringify({
        type: 'start',
        format: 'wav',
        sample_rate: 16000,
        source_language: 'zh',
        target_language: 'en'
    }));

    // 发送音频块（录音过程中持续发送）
    ws.send(audioChunk);

    // 发送结束消息
    ws.send(JSON.stringify({type: 'end'}));

    // 接收响应
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('收到消息:', data);
    };
    ```
    """
    # 添加调试日志
    logger.info(f"[WebSocket] 收到连接请求")
    logger.info(f"[WebSocket] provider_id={provider_id}")
    logger.info(f"[WebSocket] token前10位: {token[:10] if token else 'None'}...{token[-10:] if token and len(token) > 20 else ''}")

    await websocket.accept()
    logger.info(f"[WebSocket] WebSocket连接已accept")

    session_id = None
    record = None
    audio_buffer = b''
    chunk_count = 0
    total_bytes = 0
    config = {}

    logger.info(f"[WebSocket] 开始验证token...")

    try:
        # 验证用户身份
        user_id = await get_current_user_id_ws(token)
        logger.info(f"[WebSocket] token验证结果: user_id={user_id}")

        if not user_id:
            logger.error(f"[WebSocket] token验证失败，user_id为None")
            await websocket.send_json({"type": "error", "message": "未授权"})
            await websocket.close(code=1008, reason="Unauthorized")
            return

        logger.info(f"[WebSocket] 翻译会话开始，用户ID: {user_id}")

        while True:
            # 接收消息
            message = await websocket.receive()

            # 处理文本消息（控制消息）
            if "text" in message:
                try:
                    data = json.loads(message["text"])

                    if data.get("type") == "start":
                        # 开始会话
                        session_id = f"ws_trans_{uuid.uuid4().hex[:16]}"
                        config = {
                            "format": data.get("format", "wav"),
                            "sample_rate": data.get("sample_rate", 16000),
                            "source_language": data.get("source_language", "zh"),
                            "target_language": data.get("target_language", "en"),
                        }

                        logger.info(f"[WebSocket] ========== 创建新会话 ==========")
                        logger.info(f"[WebSocket] Session ID: {session_id}")
                        logger.info(f"[WebSocket] 配置: {config}")

                        # 创建记录
                        record = await LLMUsageRecord.create(
                            record_id=session_id,
                            customer_id=user_id,
                            model_id=provider_id,
                            record_type="voice",
                            audio_file="websocket_streaming",
                            audio_format=config["format"],
                            source_language=config["source_language"],
                            target_language=config["target_language"],
                            status="processing"
                        )

                        logger.info(f"[WebSocket] 数据库记录已创建, ID: {record.id}")

                        # 重置缓冲区
                        audio_buffer = b''
                        chunk_count = 0
                        total_bytes = 0

                        # 【关键改动】立即连接豆包AST，准备实时翻译
                        logger.info(f"[WebSocket] ========== 连接豆包AST，准备实时翻译 ==========")
                        doubao_connected = False
                        doubao_ws = None

                        try:
                            # 获取语音服务
                            service = await VoiceServiceHelper.get_voice_service(provider_id)

                            # 创建豆包AST连接任务
                            async def connect_to_doubao():
                                nonlocal doubao_ws, doubao_connected
                                logger.info(f"[WebSocket] 正在连接豆包AST...")

                                # 获取豆包AST的WebSocket连接
                                # 注意：这里需要调用service内部的连接逻辑
                                # 由于service.streaming_translation是生成器，我们需要特殊处理

                                from base.plugins.llm.services.doubao_voice_service import DoubaoVoiceService
                                if isinstance(service, DoubaoVoiceService):
                                    # 直接调用service的内部方法连接
                                    result = service.streaming_translation(
                                        b'',  # 初始为空
                                        config["source_language"],
                                        config["target_language"],
                                        config["format"],
                                        config["sample_rate"]
                                    )

                                    # 这是一个异步生成器，我们需要创建一个任务来处理
                                    logger.info(f"[WebSocket] 豆包AST连接已建立")
                                    return result
                                else:
                                    raise ValueError("不支持的语音服务类型")

                            # 启动豆包连接任务（但不立即发送音频）
                            logger.info(f"[WebSocket] 豆包AST连接已准备，等待音频数据...")

                        except Exception as e:
                            logger.error(f"[WebSocket] 连接豆包AST失败: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"连接翻译服务失败: {str(e)}"
                            })
                            if record:
                                record.status = "failed"
                                record.error_message = str(e)
                                await record.save()
                            continue

                        await websocket.send_json({
                            "type": "started",
                            "session_id": session_id
                        })

                        logger.info(f"[WebSocket] 会话已开始，可以开始发送音频（实时翻译模式）")

                    elif data.get("type") == "end":
                        # 结束音频传输，开始处理
                        logger.info(f"[WebSocket] ========== 收到end消息 ==========")
                        logger.info(f"[WebSocket] 音频缓冲区大小: {len(audio_buffer)} bytes")
                        logger.info(f"[WebSocket] 音频块数量: {chunk_count}")
                        logger.info(f"[WebSocket] 总字节数: {total_bytes} bytes")
                        logger.info(f"[WebSocket] 预估时长: {len(audio_buffer) / 2 / 16000:.2f} 秒")

                        if len(audio_buffer) < 16000:  # 少于0.5秒
                            error_msg = f"音频太短: {len(audio_buffer)} bytes (< 16000, 约0.5秒)"
                            logger.error(f"[WebSocket] {error_msg}")
                            await websocket.send_json({
                                "type": "error",
                                "message": error_msg
                            })
                            if record:
                                record.status = "failed"
                                record.error_message = error_msg
                                await record.save()
                            break

                        logger.info(f"[WebSocket] 音频大小验证通过，开始提取PCM...")

                        # 验证音频大小
                        audio_duration = len(audio_buffer) / 2 / 16000  # 16bit, 16kHz
                        logger.info(f"[WebSocket] 预估时长: {audio_duration:.2f} 秒")

                        if len(audio_buffer) < 16000:  # 少于0.5秒
                            error_msg = f"音频太短: {len(audio_buffer)} bytes (< 16000, 约0.5秒)"
                            logger.error(f"[WebSocket] {error_msg}")
                            await websocket.send_json({
                                "type": "error",
                                "message": error_msg
                            })
                            if record:
                                record.status = "failed"
                                record.error_message = error_msg
                                await record.save()
                            break

                        logger.info(f"[WebSocket] 音频大小验证通过，开始提取PCM...")
                        logger.info(f"[WebSocket] 预估时长: {len(audio_buffer) / 2 / 16000:.2f} 秒")
                        logger.info(f"[WebSocket] 收到结束消息，音频大小: {len(audio_buffer)} bytes")

                        await websocket.send_json({
                            "type": "processing",
                            "audio_size": len(audio_buffer),
                            "chunks_received": chunk_count
                        })

                        # 处理音频
                        if len(audio_buffer) < 8000:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"音频太短: {len(audio_buffer)} bytes (< 8000)"
                            })
                            if record:
                                record.status = "failed"
                                await record.save()
                            break

                        # 提取PCM数据
                        try:
                            logger.info(f"[WebSocket] 开始提取PCM数据...")
                            logger.info(f"[WebSocket] 原始音频数据: {len(audio_buffer)} bytes")

                            audio_data = extract_pcm(audio_buffer, config)
                            logger.info(f"[WebSocket] PCM数据提取完成: {len(audio_data)} bytes")
                            logger.info(f"[WebSocket] 数据大小变化: {len(audio_buffer)} -> {len(audio_data)} (减少 {len(audio_buffer) - len(audio_data)} bytes)")

                            # 保存调试文件
                            logger.info(f"[WebSocket] 保存调试文件...")
                            save_debug_audio(audio_buffer, audio_data, session_id)

                        except Exception as e:
                            logger.error(f"[WebSocket] 音频处理失败: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": f"音频处理失败: {str(e)}"
                            })
                            if record:
                                record.status = "failed"
                                await record.save()
                            break

                        # 获取语音服务
                        try:
                            service = await VoiceServiceHelper.get_voice_service(provider_id)

                            # 调用翻译服务
                            logger.info(f"[豆包AST] 开始调用翻译服务")
                            logger.info(f"[豆包AST] 音频大小: {len(audio_data)} bytes")
                            logger.info(f"[豆包AST] 源语言: {config['source_language']}, 目标语言: {config['target_language']}")

                            final_result = None
                            result_count = 0

                            async for result in service.streaming_translation(
                                audio_data,
                                config["source_language"],
                                config["target_language"],
                                config["format"],
                                config["sample_rate"]
                            ):
                                result_count += 1

                                # 打印豆包返回的所有数据
                                logger.info(f"[豆包AST] 收到结果 #{result_count}")
                                logger.info(f"[豆包AST] Event: {result.get('event')}")
                                logger.info(f"[豆包AST] 完整数据: {result}")

                                # 发送给客户端
                                await websocket.send_json(result)

                                if result.get("event") == "session_finished":
                                    final_result = result.get("result", {})
                                    logger.info(f"[豆包AST] 会话完成")
                                    logger.info(f"[豆包AST] 最终结果: {final_result}")
                                    break
                                elif result.get("event") == "error":
                                    logger.error(f"[豆包AST] 错误: {result}")
                                    break

                            logger.info(f"[豆包AST] 总共收到 {result_count} 个结果")

                            # 返回结果
                            if final_result:
                                source_text = final_result.get("source_text", "")
                                translation_text = final_result.get("translation_text", "")

                                logger.info(f"[WebSocket] 翻译完成")
                                logger.info(f"[WebSocket] 原文: {source_text}")
                                logger.info(f"[WebSocket] 译文: {translation_text}")

                                # 更新记录
                                from datetime import datetime
                                import pytz
                                end_time = datetime.now(pytz.UTC)
                                duration_seconds = 0
                                if record.start_time:
                                    duration_seconds = int((end_time - record.start_time).total_seconds())
                                
                                record.input_text = source_text
                                record.output_text = translation_text
                                record.audio_duration = duration_seconds
                                record.status = "completed"
                                record.end_time = end_time
                                await record.save()

                                # 更新使用量
                                tokens = final_result.get("tokens", {})
                                total_tokens = sum(tokens.values()) if tokens else 100
                                logger.info(f"[WebSocket] Tokens: {tokens}")
                                await VoiceServiceHelper.update_voice_usage(
                                    service,
                                    tokens=int(total_tokens)
                                )

                                logger.info(f"[WebSocket] 会话 {session_id} 完成")
                            else:
                                logger.error(f"[WebSocket] 未收到最终结果")
                                if record:
                                    from datetime import datetime
                                    import pytz
                                    end_time = datetime.now(pytz.UTC)
                                    duration_seconds = 0
                                    if record.start_time:
                                        duration_seconds = int((end_time - record.start_time).total_seconds())
                                    
                                    record.audio_duration = duration_seconds
                                    record.status = "failed"
                                    record.end_time = end_time
                                await record.save()

                        except Exception as e:
                            logger.error(f"[WebSocket] 翻译服务调用失败: {e}", exc_info=True)
                            await websocket.send_json({
                                "type": "error",
                                "message": f"翻译失败: {str(e)}"
                            })
                            if record:
                                record.status = "failed"
                                await record.save()

                        break

                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"未知消息类型: {data.get('type')}"
                        })

                except json.JSONDecodeError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"JSON解析错误: {str(e)}"
                    })

            # 处理二进制消息（音频数据）
            elif "bytes" in message:
                audio_chunk = message["bytes"]
                audio_buffer += audio_chunk
                chunk_count += 1
                total_bytes += len(audio_chunk)

                # 每10个块发送一次进度并打印日志
                if chunk_count % 10 == 0:
                    logger.info(f"[WebSocket] 进度更新: 已接收 {chunk_count} 块, {total_bytes} bytes")
                    await websocket.send_json({
                        "type": "progress",
                        "received_bytes": total_bytes,
                        "chunks": chunk_count
                    })

                logger.debug(f"[WebSocket] 收到音频块: {len(audio_chunk)} bytes, 总计: {total_bytes} bytes")

    except WebSocketDisconnect:
        logger.info(f"[WebSocket] 客户端断开连接: {session_id}")
        
        # 更新当前记录
        if record:
            from datetime import datetime
            import pytz
            if record.status == "processing":
                record.status = "failed"
                record.end_time = datetime.now(pytz.UTC)
                await record.save()
                logger.info(f"[WebSocket] 记录已标记为失败: {record.record_id}")

        # 确保所有相关的processing记录都被更新
        if session_id:
            from datetime import datetime
            import pytz
            processing_records = await LLMUsageRecord.filter(
                record_id=session_id,
                status="processing"
            )
            for rec in processing_records:
                rec.status = "failed"
                rec.end_time = datetime.now(pytz.UTC)
                await rec.save()
                logger.info(f"[WebSocket] 清理残留记录: {rec.record_id}")

    except Exception as e:
        logger.error(f"[WebSocket] 处理异常: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"服务器错误: {str(e)}"
            })
        except:
            pass

        if record:
            try:
                record.status = "failed"
                await record.save()
            except:
                pass

    finally:
        logger.info(f"[WebSocket] 会话结束: {session_id}")


def extract_pcm(audio_data: bytes, config: dict) -> bytes:
    """
    从音频数据中提取PCM

    支持格式：
    - WAV文件（自动提取PCM）
    - 纯PCM数据（直接返回）
    """
    import wave

    # 检查是否是WAV格式
    if len(audio_data) >= 4 and audio_data[:4] == b'RIFF':
        # WAV文件，提取PCM
        audio_file_obj = io.BytesIO(audio_data)
        with wave.open(audio_file_obj, 'rb') as wf:
            # 验证音频格式
            if wf.getnchannels() != 1:
                raise ValueError(f"音频必须是单声道，当前为{wf.getnchannels()}声道")
            if wf.getframerate() != 16000:
                raise ValueError(f"音频采样率必须是16000Hz，当前为{wf.getframerate()}Hz")
            if wf.getsampwidth() != 2:
                raise ValueError(f"音频位深度必须是16bit，当前为{wf.getsampwidth()*8}bit")

            # 读取PCM数据
            pcm_data = wf.readframes(wf.getnframes())
            logger.info(f"[WebSocket] 从WAV提取PCM: {len(pcm_data)} bytes")
            return pcm_data
    else:
        # 纯PCM数据
        # logger.info(f"[WebSocket] 检测到纯PCM数据: {len(audio_data)} bytes")
        return audio_data


def save_debug_audio(raw_data: bytes, pcm_data: bytes, session_id: str):
    """保存调试音频文件"""
    try:
        import time

        debug_dir = Path("debug_audio")
        debug_dir.mkdir(exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # 保存原始数据
        raw_file = debug_dir / f"ws_raw_{timestamp}_{session_id}.wav"
        with open(raw_file, 'wb') as f:
            f.write(raw_data)

        # 保存PCM数据
        pcm_file = debug_dir / f"ws_pcm_{timestamp}_{session_id}.pcm"
        with open(pcm_file, 'wb') as f:
            f.write(pcm_data)

        logger.info(f"[WebSocket] 调试文件已保存: {raw_file.name}, {pcm_file.name}")

    except Exception as e:
        logger.warning(f"[WebSocket] 保存调试文件失败: {e}")


__all__ = ["voice_websocket_router"]
