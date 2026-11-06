"""
豆包AST服务 - 完全使用官方demo的protobuf和代码结构
直接复制官方demo的工作逻辑
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
    from products.understanding.ast.ast_service_pb2 import TranslateRequest, TranslateResponse
    from common.events_pb2 import Type
    # logger.info("[AST] 使用官方demo的protobuf定义")
else:
    logger.error(f"[AST] 官方protobuf不存在: {ast_demo_protogen}")
    raise ImportError("无法找到官方protobuf定义")


class DoubaoASTServiceV2:
    """豆包AST服务 - 完全基于官方demo"""

    def __init__(self, app_key: str, access_key: str, resource_id: str = "volc.service_type.10053"):
        self.app_key = app_key
        self.access_key = access_key
        self.resource_id = resource_id

    async def streaming_translation(
        self,
        audio_data: bytes,
        source_language: str = "zh",
        target_language: str = "en",
        format: str = "wav",
        sample_rate: int = 16000
    ) -> AsyncIterator[Dict]:
        """
        同声传译（流式）- 完全复制官方demo逻辑
        """

        logger.info(f"[AST] 接收到音频数据: {len(audio_data)} bytes")

        # 验证音频长度
        if len(audio_data) < 8000:
            error_msg = f"音频太短: {len(audio_data)} bytes (< 8000)，建议至少1秒"
            logger.error(f"[AST] {error_msg}")
            yield {
                "event": "error",
                "error": error_msg,
                "type": "AudioTooShortError"
            }
            return

        ws_url = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
        session_id = str(uuid.uuid4())
        conn_id = str(uuid.uuid4())

        # 构建请求头（与官方demo完全一致）
        headers = Headers({
            "X-Api-App-Key": self.app_key,
            "X-Api-Access-Key": self.access_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": conn_id
        })

        logger.info(f"[AST] 开始同声传译会话: {session_id}")

        try:
            # 连接服务器（与官方demo完全一致的配置）
            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                max_size=1000000000,
                ping_interval=None
            ) as ws:
                logger.info(f"[AST] WebSocket连接已建立")

                # ========== 发送StartSession（完全复制官方demo） ==========
                logger.info(f"[AST] 发送StartSession")

                request_data = TranslateRequest()
                request_data.request_meta.SessionID = session_id
                request_data.event = Type.StartSession

                # 用户信息
                request_data.user.uid = "ast_py_client"
                request_data.user.did = "ast_py_client"

                # 音频配置
                request_data.source_audio.format = "wav"
                request_data.source_audio.rate = 16000
                request_data.source_audio.bits = 16
                request_data.source_audio.channel = 1

                # 目标音频配置
                request_data.target_audio.format = "ogg_opus"
                request_data.target_audio.rate = 24000

                # 请求配置
                request_data.request.mode = "s2s"
                request_data.request.source_language = source_language
                request_data.request.target_language = target_language

                # 序列化并发送
                start_data = request_data.SerializeToString()
                await ws.send(start_data)

                logger.info(f"[AST] 已发送StartSession ({len(start_data)} bytes)")

                # ========== 等待SessionStarted ==========
                response_data = await ws.recv()
                logger.info(f"[AST] 收到响应 ({len(response_data)} bytes)")

                Response_data = TranslateResponse()
                Response_data.ParseFromString(response_data)

                if Response_data.event != Type.SessionStarted:
                    error_msg = f"会话建立失败: {Response_data.response_meta.Message}"
                    logger.error(f"[AST] {error_msg}")
                    yield {
                        "event": "error",
                        "error": error_msg,
                        "status_code": Response_data.event,
                        "type": "SessionStartError"
                    }
                    return

                logger.info(f"[AST] 会话已建立 (session_id: {session_id})")

                # ========== 发送音频数据（使用官方demo的逻辑） ==========
                chunk_size = 3200  # 官方demo: 100ms
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                logger.info(f"[AST] 发送音频数据: {len(audio_data)} bytes, 分为 {total_chunks} 块")

                # 异步发送任务
                async def send_audio_chunks():
                    try:
                        for i in range(0, len(audio_data), chunk_size):
                            chunk = audio_data[i:i + chunk_size]

                            # 构建TaskRequest（完全复制官方demo）
                            request_data = TranslateRequest()
                            request_data.request_meta.SessionID = session_id
                            request_data.event = Type.TaskRequest
                            request_data.user.uid = "ast_py_client"
                            request_data.user.did = "ast_py_client"

                            # 重要：每次都设置完整的audio信息
                            request_data.source_audio.format = "wav"
                            request_data.source_audio.rate = 16000
                            request_data.source_audio.bits = 16
                            request_data.source_audio.channel = 1

                            # 设置音频数据
                            if chunk:
                                request_data.source_audio.binary_data = chunk

                            request_data.target_audio.format = "ogg_opus"
                            request_data.target_audio.rate = 24000
                            request_data.request.mode = "s2s"
                            request_data.request.source_language = source_language
                            request_data.request.target_language = target_language

                            # 发送
                            await ws.send(request_data.SerializeToString())

                            if (i // chunk_size + 1) % 10 == 0:
                                logger.info(f"[AST] 已发送 {i // chunk_size + 1}/{total_chunks} 块")

                            # 官方demo的延迟
                            await asyncio.sleep(0.1)

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
                        logger.info(f"[AST] 已发送FinishSession")

                    except Exception as e:
                        logger.error(f"[AST] 发送音频异常: {e}")
                        raise

                # 启动发送任务
                sender_task = asyncio.create_task(send_audio_chunks())

                # ========== 接收翻译结果 ==========
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

                try:
                    while True:
                        response_data = await ws.recv()

                        Response_data = TranslateResponse()
                        Response_data.ParseFromString(response_data)

                        # 处理不同事件
                        if Response_data.event == Type.SessionFailed or Response_data.event == Type.SessionCanceled:
                            error_msg = Response_data.response_meta.Message
                            logger.error(f"[AST] 会话失败: {error_msg}")
                            yield {
                                "event": "error",
                                "error": error_msg,
                                "error_code": str(Response_data.event),
                                "type": "SessionFailedError"
                            }
                            break

                        if Response_data.event == Type.SessionFinished:
                            logger.info(f"[AST] 会话正常结束")
                            final_result["source_text"] = " ".join(final_result["source_segments"])
                            final_result["translation_text"] = " ".join(final_result["translation_segments"])

                            yield {
                                "event": "session_finished",
                                "result": final_result
                            }
                            break

                        # 处理UsageResponse
                        if Response_data.event == Type.UsageResponse:
                            response_dict = MessageToDict(Response_data)
                            logger.info(f"[AST] 计费信息: {json.dumps(response_dict, indent=2, ensure_ascii=False)}")
                            final_result["tokens"] = response_dict
                        else:
                            # 处理翻译结果
                            if Response_data.text:
                                # 检查事件类型，区分原文和译文
                                if Response_data.event == Type.SourceSubtitleResponse:
                                    final_result["source_segments"].append(Response_data.text)
                                    logger.info(f"[AST] 原文: {Response_data.text}")
                                else:
                                    final_result["translation_segments"].append(Response_data.text)
                                    logger.info(f"[AST] 翻译: {Response_data.text}")

                                yield {
                                    "event": "translation",
                                    "text": Response_data.text,
                                    "sequence": Response_data.response_meta.Sequence
                                }

                            if Response_data.data:
                                final_result["audio_data"] += Response_data.data

                except Exception as e:
                    logger.error(f"[AST] 接收消息异常: {e}")
                    raise

                finally:
                    await sender_task

        except Exception as e:
            logger.error(f"[AST] 同声传译失败: {str(e)}", exc_info=True)
            raise
