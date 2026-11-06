"""
豆包AST服务 - 使用官方demo的完整实现
替换现有的DoubaoVoiceService.streaming_translation方法
"""
import asyncio
import uuid
import logging
import sys
from pathlib import Path
from typing import AsyncIterator, Dict
import websockets
from websockets import Headers
from google.protobuf.json_format import MessageToDict
import json

logger = logging.getLogger(__name__)

# 添加官方demo的protobuf路径
ast_demo_protogen = Path(__file__).parent.parent.parent.parent.parent / "python_protogen"
if ast_demo_protogen.exists():
    sys.path.insert(0, str(ast_demo_protogen))
    try:
        from products.understanding.ast.ast_service_pb2 import TranslateRequest, TranslateResponse
        from common.events_pb2 import Type
        # logger.info("[AST] 使用官方demo的protobuf定义")
        USE_OFFICIAL_PROTO = True
    except ImportError as e:
        logger.warning(f"[AST] 无法导入官方protobuf: {e}")
        USE_OFFICIAL_PROTO = False
else:
    logger.warning(f"[AST] 官方protobuf不存在: {ast_demo_protogen}")
    USE_OFFICIAL_PROTO = False


async def streaming_translation_official(self, audio_data: bytes, source_language: str = "zh",
                                        target_language: str = "en", format: str = "wav",
                                        sample_rate: int = 16000, asr_config: dict = None,
                                        llm_config: dict = None) -> AsyncIterator[Dict]:
    """
    同声传译（流式）- 使用官方demo的实现

    这是DoubaoVoiceService.streaming_translation的替换版本
    使用官方demo的protobuf和代码逻辑
    """
    if not USE_OFFICIAL_PROTO:
        logger.error("[AST] 官方protobuf不可用，无法使用官方demo实现")
        yield {
            "event": "error",
            "error": "官方protobuf不可用，请确保tests/ast_python/python_protogen存在",
            "type": "ProtobufNotAvailableError"
        }
        return

    logger.info(f"[AST官方实现] 接收到音频数据: {len(audio_data)} bytes")

    

    # 验证音频长度
    if len(audio_data) < 8000:
        error_msg = f"音频太短: {len(audio_data)} bytes (< 8000)，建议至少1秒"
        logger.error(f"[AST] {error_msg}")
        yield {
            "event": "error",
            "error": error_msg,
            "type": "AudioTooShortError"
        }
        return  # 保持return，这是正确的

    ws_url = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
    session_id = str(uuid.uuid4())
    conn_id = str(uuid.uuid4())

    headers = Headers({
        "X-Api-App-Key": self.api_id or self.api_key,
        "X-Api-Access-Key": self.access_token or self.api_key,
        "X-Api-Resource-Id": "volc.service_type.10053",
        "X-Api-Connect-Id": conn_id
    })

    logger.info(f"[AST官方实现] 会话ID: {session_id}")
    logger.info(f"[AST官方实现] 源语言: {source_language}, 目标语言: {target_language}")
    logger.info(f"[AST官方实现] 音频大小: {len(audio_data)} bytes")

    # 添加重试机制
    max_retries = 2
    base_delay = 3

    for retry_count in range(max_retries):
        try:
            if retry_count > 0:
                logger.info(f"[AST官方实现] 重试连接 #{retry_count + 1}/{max_retries}...")
                await asyncio.sleep(base_delay)

            logger.info(f"[AST官方实现] 开始 WebSocket 连接...")
            import time
            start_time = time.time()

            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                max_size=1000000000,
                ping_interval=None,
                close_timeout=30,  # 30秒关闭超时
            ) as ws:
                elapsed = time.time() - start_time
                logger.info(f"[AST官方实现] ✅ WebSocket连接已建立 (耗时: {elapsed:.2f}秒)")

                # 发送StartSession
                request_data = TranslateRequest()
                request_data.request_meta.SessionID = session_id
                request_data.event = Type.StartSession
                request_data.user.uid = "ast_py_client"
                request_data.user.did = "ast_py_client"
                request_data.source_audio.format = "wav"
                request_data.source_audio.rate = 16000
                request_data.source_audio.bits = 16
                request_data.source_audio.channel = 1
                request_data.target_audio.format = "ogg_opus"
                request_data.target_audio.rate = 24000
                request_data.request.mode = "s2s"
                request_data.request.source_language = source_language
                request_data.request.target_language = target_language

                start_data = request_data.SerializeToString()
                await ws.send(start_data)

                logger.info(f"[AST官方实现] StartSession已发送")

                # 等待SessionStarted
                response_data = await ws.recv()
                Response_data = TranslateResponse()
                Response_data.ParseFromString(response_data)

                if Response_data.event != Type.SessionStarted:
                    error_msg = f"会话建立失败: {Response_data.response_meta.Message}"
                    logger.error(f"[AST官方实现] {error_msg}")
                    yield {
                        "event": "error",
                        "error": error_msg,
                        "status_code": Response_data.event,
                        "type": "SessionStartError"
                    }
                    return

                logger.info(f"[AST官方实现] 会话已建立")

                # 发送音频
                chunk_size = 3200
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                logger.info(f"[AST官方实现] 发送音频: {len(audio_data)} bytes, {total_chunks} 块")

                async def send_audio_chunks():
                    try:
                        for i in range(0, len(audio_data), chunk_size):
                            chunk = audio_data[i:i + chunk_size]

                            request_data = TranslateRequest()
                            request_data.request_meta.SessionID = session_id
                            request_data.event = Type.TaskRequest
                            request_data.user.uid = "ast_py_client"
                            request_data.user.did = "ast_py_client"
                            request_data.source_audio.format = "wav"
                            request_data.source_audio.rate = 16000
                            request_data.source_audio.bits = 16
                            request_data.source_audio.channel = 1
                            if chunk:
                                request_data.source_audio.binary_data = chunk
                            request_data.target_audio.format = "ogg_opus"
                            request_data.target_audio.rate = 24000
                            request_data.request.mode = "s2s"
                            request_data.request.source_language = source_language
                            request_data.request.target_language = target_language

                            await ws.send(request_data.SerializeToString())

                            if (i // chunk_size + 1) % 10 == 0:
                                logger.info(f"[AST官方实现] 已发送 {i // chunk_size + 1}/{total_chunks} 块")

                            await asyncio.sleep(0.01)  # 减少延迟，加快发送速度

                        # 发送FinishSession
                        request_data = TranslateRequest()
                        request_data.request_meta.SessionID = session_id
                        request_data.event = Type.FinishSession
                        request_data.user.uid = "ast_py_client"
                        request_data.user.did = "ast_py_client"
                        request_data.source_audio.format = "wav"
                        request_data.source_audio.rate = 16000
                        request_data.source_audio.bits = 16
                        request_data.source_audio.channel = 1
                        request_data.target_audio.format = "ogg_opus"
                        request_data.target_audio.rate = 24000

                        await ws.send(request_data.SerializeToString())
                        logger.info(f"[AST官方实现] FinishSession已发送")

                    except Exception as e:
                        logger.error(f"[AST官方实现] 发送异常: {e}")
                        raise

                sender_task = asyncio.create_task(send_audio_chunks())

                # 接收结果
                final_result = {
                    "session_id": session_id,
                    "source_text": "",
                    "translation_text": "",
                    "source_segments": [],
                    "translation_segments": [],
                    "audio_data": b"",
                    "tokens": {},
                    "duration_ms": 0
                }

                # 用于断句对齐的临时变量
                source_buffer = []
                translation_buffer = []
                pending_source = ""
                pending_translation = ""

                try:
                    while True:
                        response_data = await ws.recv()
                        Response_data = TranslateResponse()
                        Response_data.ParseFromString(response_data)

                        if Response_data.event == Type.SessionFailed:
                            error_msg = Response_data.response_meta.Message
                            logger.error(f"[AST官方实现] 会话失败: {error_msg}")
                            yield {
                                "event": "error",
                                "error": error_msg,
                                "error_code": str(Response_data.event),
                                "type": "SessionFailedError"
                            }
                            break

                        if Response_data.event == Type.SessionFinished:
                            logger.info(f"[AST官方实现] 会话完成")
                            # 处理最后一个片段
                            if pending_source:
                                source_buffer.append(pending_source)
                            if pending_translation:
                                translation_buffer.append(pending_translation)
                            
                            # 确保断句数量一致
                            while len(source_buffer) < len(translation_buffer):
                                source_buffer.append("")
                            while len(translation_buffer) < len(source_buffer):
                                translation_buffer.append("")
                            
                            final_result["source_segments"] = source_buffer
                            final_result["translation_segments"] = translation_buffer
                            final_result["source_text"] = " ".join(source_buffer)
                            final_result["translation_text"] = " ".join(translation_buffer)
                            yield {
                                "event": "session_finished",
                                "result": final_result
                            }
                            break

                        if Response_data.event == Type.UsageResponse:
                            response_dict = MessageToDict(Response_data)
                            final_result["tokens"] = response_dict
                        else:
                            # 处理原文事件
                            if Response_data.event == 651:  # SourceSubtitleResponse
                                pending_source += Response_data.text
                                logger.info(f"[AST官方实现] 原文: {Response_data.text}")
                            elif Response_data.event == 652:  # SourceSubtitleEnd
                                if pending_source:
                                    source_buffer.append(pending_source)
                                    pending_source = ""
                                logger.info(f"[AST官方实现] 原文片段结束")
                            # 处理译文事件
                            elif Response_data.event == 654:  # TranslationSubtitleResponse
                                pending_translation += Response_data.text
                                logger.info(f"[AST官方实现] 译文: {Response_data.text}")
                            elif Response_data.event == 655:  # TranslationSubtitleEnd
                                if pending_translation:
                                    translation_buffer.append(pending_translation)
                                    pending_translation = ""
                                logger.info(f"[AST官方实现] 译文片段结束")
                            # 处理其他文本事件（兼容旧版）
                            elif Response_data.text and Response_data.event not in [651, 652, 654, 655]:
                                translation_buffer.append(Response_data.text)
                                logger.info(f"[AST官方实现] 翻译: {Response_data.text}")
                                yield {
                                    "event": "translation",
                                    "text": Response_data.text,
                                    "sequence": Response_data.response_meta.Sequence
                                }

                            if Response_data.data:
                                final_result["audio_data"] += Response_data.data

                except Exception as e:
                    logger.error(f"[AST官方实现] 接收异常: {e}")
                    raise

                finally:
                    await sender_task

            # 如果成功连接并处理完成，跳出重试循环
            break

        except (asyncio.TimeoutError, TimeoutError, OSError, ConnectionError) as e:
            # 连接相关错误，尝试重试
            logger.warning(f"[AST官方实现] 连接异常: {type(e).__name__}: {e}")
            if retry_count < max_retries - 1:
                logger.info(f"[AST官方实现] 准备重试... ({retry_count + 1}/{max_retries})")
                continue
            else:
                logger.error(f"[AST官方实现] 达到最大重试次数，放弃连接")
                yield {
                    "event": "error",
                    "error": f"连接豆包AST失败，已重试 {max_retries} 次: {str(e)}",
                    "type": "ConnectionError"
                }
                return

        except Exception as e:
            # 其他未知错误
            logger.error(f"[AST官方实现] 未知错误: {str(e)}", exc_info=True)
            yield {
                "event": "error",
                "error": f"AST实现错误: {str(e)}",
                "type": "ASTImplementationError"
            }
            return


#  Monkey patch：替换DoubaoVoiceService的streaming_translation方法
try:
    from base.plugins.llm.services import doubao_voice_service
    original_method = doubao_voice_service.DoubaoVoiceService.streaming_translation
    doubao_voice_service.DoubaoVoiceService.streaming_translation = streaming_translation_official
    logger.info("[AST] 已替换DoubaoVoiceService.streaming_translation为官方demo实现")
except Exception as e:
    logger.error(f"[AST] 无法替换streaming_translation方法: {e}")
