"""
豆包AST同声传译服务 - 基于官方Demo优化版本
参考: tests/ast_python/ast_demo.py
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

# 尝试导入官方Protobuf定义
# python_protogen 现在在项目根目录，可以直接作为包导入
try:
    from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest, TranslateResponse
    from python_protogen.common.events_pb2 import Type
    logger.info("[AST] 使用官方Protobuf定义")
    USE_OFFICIAL_PROTOBUF = True
except ImportError as e:
    logger.warning(f"[AST] 无法导入官方Protobuf: {e}，使用本地版本")
    USE_OFFICIAL_PROTOBUF = False

# 如果官方protobuf不可用，使用本地版本
if not USE_OFFICIAL_PROTOBUF:
    try:
        from base.plugins.llm.services.protobuf import doubao_ast_pb2
        logger.info("[AST] 使用本地Protobuf定义")

        # 创建兼容层
        class Type:
            StartSession = 100
            TaskRequest = 200
            FinishSession = 102
            SessionStarted = 150
            SessionFinished = 152
            SessionFailed = 153
            UsageResponse = 154

        class TranslateRequest:
            def __init__(self):
                self.request_meta = type('obj', (object,), {
                    'SessionID': '',
                    'Sequence': 0
                })()
                self.event = 0
                self.user = type('obj', (object,), {
                    'uid': '',
                    'did': ''
                })()
                self.source_audio = type('obj', (object,), {
                    'format': '',
                    'rate': 0,
                    'bits': 0,
                    'channel': 0,
                    'binary_data': b''
                })()
                self.target_audio = type('obj', (object,), {
                    'format': '',
                    'rate': 0
                })()
                self.request = type('obj', (object,), {
                    'mode': '',
                    'source_language': '',
                    'target_language': '',
                    'service_name': ''
                })()
                self.text = ''
                self.data = b''
                self.spk_chg = False

            def SerializeToString(self):
                # 使用本地protobuf序列化
                import struct
                if self.event == Type.StartSession:
                    msg = doubao_ast_pb2.StartSessionRequest()
                    msg.request_meta.session_id = self.request_meta.SessionID
                    msg.event = Type.StartSession
                    msg.user.uid = self.user.uid
                    msg.user.did = self.user.did
                    msg.request.mode = self.request.mode
                    msg.request.source_language = self.request.source_language
                    msg.request.target_language = self.request.target_language
                    msg.request.service_name = self.request.service_name
                    msg.source_audio.format = self.source_audio.format
                    msg.source_audio.codec = "raw"
                    msg.source_audio.rate = self.source_audio.rate
                    msg.source_audio.bits = self.source_audio.bits
                    msg.source_audio.channel = self.source_audio.channel
                    msg.target_audio.format = self.target_audio.format
                    msg.target_audio.rate = self.target_audio.rate
                elif self.event == Type.TaskRequest:
                    msg = doubao_ast_pb2.TaskRequest()
                    msg.event = Type.TaskRequest
                    msg.source_audio.data = self.source_audio.binary_data
                elif self.event == Type.FinishSession:
                    msg = doubao_ast_pb2.FinishSessionRequest()
                    msg.event = Type.FinishSession

                return msg.SerializeToString()

        class TranslateResponse:
            def __init__(self):
                self.event = 0
                self.response_meta = type('obj', (object,), {
                    'SessionID': '',
                    'Sequence': 0,
                    'Message': ''
                })()
                self.text = ''
                self.data = b''
                self.spk_chg = False

            def ParseFromString(self, data):
                # 尝试解析为不同类型 - 使用正确的类名
                response_types = [
                    (doubao_ast_pb2.SessionStartedResponse, Type.SessionStarted),
                    (doubao_ast_pb2.SourceSubtitleResponse, Type.TaskRequest),
                    (doubao_ast_pb2.TranslationSubtitleResponse, Type.TaskRequest),  # 使用Translation而不是Target
                    (doubao_ast_pb2.SessionFinishedResponse, Type.SessionFinished),  # 使用Response后缀
                    (doubao_ast_pb2.SessionFailedResponse, Type.SessionFailed),      # 使用Response后缀
                    (doubao_ast_pb2.UsageResponse, Type.UsageResponse),
                ]

                # 直接使用这些类，因为它们已经验证存在
                for resp_class, event_type in response_types:
                    try:
                        msg = resp_class()
                        msg.ParseFromString(data)
                        logger.debug(f"[AST] 成功解析为: {resp_class.__name__}")

                        # 根据响应类型设置正确的event值
                        self.event = event_type

                        if hasattr(msg, 'response_meta'):
                            self.response_meta.SessionID = msg.response_meta.session_id
                            self.response_meta.Sequence = getattr(msg.response_meta, 'sequence', 0)
                            self.response_meta.Message = msg.response_meta.message if hasattr(msg.response_meta, 'message') else ''

                        if hasattr(msg, 'source_subtitle') and msg.source_subtitle.text:
                            self.text = msg.source_subtitle.text
                        elif hasattr(msg, 'target_subtitle') and msg.target_subtitle.text:
                            self.text = msg.target_subtitle.text
                        elif hasattr(msg, 'data'):
                            self.data = msg.data
                            self.spk_chg = getattr(msg, 'spk_chg', False)

                        return True
                    except:
                        continue

                return False

    except ImportError:
        logger.error("[AST] 无法导入任何Protobuf定义")
        raise


class DoubaoASTOfficialService:
    """豆包AST服务 - 基于官方Demo优化版本"""

    def __init__(self, app_key: str, access_key: str, resource_id: str = "volc.service_type.10053"):
        self.app_key = app_key
        self.access_key = access_key
        self.resource_id = resource_id

    @staticmethod
    async def test_connection(app_key: str, access_key: str, resource_id: str = "volc.service_type.10053") -> bool:
        """
        测试豆包AST连接是否正常

        Returns:
            bool: 连接是否成功
        """
        import socket
        import time

        logger.info(f"[AST连接测试] 开始测试...")
        start_time = time.time()

        # 1. 测试TCP连接
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(10)
            result = test_socket.connect_ex(("openspeech.bytedance.com", 443))
            test_socket.close()

            if result != 0:
                logger.error(f"[AST连接测试] TCP连接失败: {result}")
                return False

            logger.info(f"[AST连接测试] TCP连接成功")
        except Exception as e:
            logger.error(f"[AST连接测试] TCP连接异常: {e}")
            return False

        # 2. 测试WebSocket握手
        try:
            ws_url = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
            conn_id = f"test-connection-{int(time.time())}"

            headers = Headers({
                "X-Api-App-Key": app_key,
                "X-Api-Access-Key": access_key,
                "X-Api-Resource-Id": resource_id,
                "X-Api-Connect-Id": conn_id
            })

            logger.info(f"[AST连接测试] 开始WebSocket握手...")
            ws_start = time.time()

            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                max_size=1000000000,
                ping_interval=None,
                close_timeout=30
            ) as ws:
                elapsed = time.time() - ws_start
                logger.info(f"[AST连接测试] ✅ WebSocket握手成功 (耗时: {elapsed:.2f}秒)")

                # 保持连接1秒测试稳定性
                await asyncio.sleep(1)
                logger.info(f"[AST连接测试] ✅ 连接稳定")

                return True

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"[AST连接测试] ⏰ 连接超时 (总耗时: {elapsed:.2f}秒)")
            return False
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[AST连接测试] ❌ 连接失败 (耗时: {elapsed:.2f}秒): {e}")
            return False

    async def streaming_translation(
        self,
        audio_data: bytes,
        source_language: str = "zh",
        target_language: str = "en",
        format: str = "wav",
        sample_rate: int = 16000
    ) -> AsyncIterator[Dict]:
        """
        同声传译（流式）

        Args:
            audio_data: 音频数据
            source_language: 源语言 (zh/en)
            target_language: 目标语言 (zh/en)
            format: 音频格式 (wav)
            sample_rate: 采样率 (16000)

        Yields:
            翻译结果字典
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

        # 构建请求头（与官方demo一致）
        headers = Headers({
            "X-Api-App-Key": self.app_key,
            "X-Api-Access-Key": self.access_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": conn_id  # 官方demo包含此字段
        })

        logger.info(f"[AST] 开始同声传译会话: {session_id}")
        logger.info(f"[AST] 源语言: {source_language}, 目标语言: {target_language}")

        import time
        connection_start_time = time.time()

        try:
            # 连接服务器（使用官方demo的配置）
            # 增加超时设置和连接参数以应对网络问题
            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                max_size=1000000000,  # 1GB
                ping_interval=None,  # 官方demo设置为None
                close_timeout=30,  # 30秒关闭超时
                # 网络问题：尝试更长的连接超时
            ) as ws:
                connection_elapsed = time.time() - connection_start_time
                logger.info(f"[AST] ✅ WebSocket连接已建立 (耗时: {connection_elapsed:.2f}秒)")
                logger.info(f"[AST] 连接参数: URL={ws_url}, Connect-ID={conn_id}")

                # ========== 步骤1: 发送StartSession ==========
                logger.info(f"[AST] 发送StartSession")

                start_request = TranslateRequest()
                start_request.request_meta.SessionID = session_id
                start_request.event = Type.StartSession

                # 用户信息
                start_request.user.uid = "ast_py_client"
                start_request.user.did = "ast_py_client"

                # 音频配置
                start_request.source_audio.format = "wav"
                start_request.source_audio.rate = 16000
                start_request.source_audio.bits = 16
                start_request.source_audio.channel = 1

                # 目标音频配置
                start_request.target_audio.format = "ogg_opus"
                start_request.target_audio.rate = 24000

                # 请求配置
                start_request.request.mode = "s2s"
                start_request.request.source_language = source_language
                start_request.request.target_language = target_language

                # 序列化并发送
                start_data = start_request.SerializeToString()
                await ws.send(start_data)

                logger.info(f"[AST] 已发送StartSession ({len(start_data)} bytes)")

                # ========== 步骤2: 等待SessionStarted ==========
                response_data = await ws.recv()
                logger.info(f"[AST] 收到响应 ({len(response_data)} bytes)")

                response = TranslateResponse()
                response.ParseFromString(response_data)

                if response.event != Type.SessionStarted:
                    error_msg = f"会话建立失败: {response.response_meta.Message}"
                    logger.error(f"[AST] {error_msg}")
                    yield {
                        "event": "error",
                        "error": error_msg,
                        "status_code": response.event,
                        "type": "SessionStartError"
                    }
                    return

                logger.info(f"[AST] 会话已建立 (session_id: {session_id})")

                # ========== 步骤3: 发送音频数据 ==========
                # 使用官方demo的分块大小：3200 bytes (100ms)
                chunk_size = 3200
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                logger.info(f"[AST] 发送音频数据: {len(audio_data)} bytes, 分为 {total_chunks} 块")

                # 异步发送音频任务
                async def send_audio_chunks():
                    try:
                        for i in range(0, len(audio_data), chunk_size):
                            chunk = audio_data[i:i + chunk_size]

                            task_request = TranslateRequest()
                            task_request.event = Type.TaskRequest
                            task_request.source_audio.binary_data = chunk

                            task_data = task_request.SerializeToString()
                            await ws.send(task_data)

                            if (i // chunk_size + 1) % 10 == 0:
                                logger.info(f"[AST] 已发送 {i // chunk_size + 1}/{total_chunks} 块")

                            # 关键修改：使用官方demo的延迟 (0.1秒)
                            await asyncio.sleep(0.1)

                        # 发送FinishSession
                        finish_request = TranslateRequest()
                        finish_request.event = Type.FinishSession

                        finish_data = finish_request.SerializeToString()
                        await ws.send(finish_data)

                        logger.info(f"[AST] 已发送FinishSession")

                    except Exception as e:
                        logger.error(f"[AST] 发送音频异常: {e}")
                        raise

                # 启动发送任务
                sender_task = asyncio.create_task(send_audio_chunks())

                # ========== 步骤4: 接收翻译结果 ==========
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

                        response = TranslateResponse()
                        response.ParseFromString(response_data)

                        # 处理不同类型的事件
                        if response.event == Type.SessionFailed:
                            error_msg = response.response_meta.Message or "会话失败"
                            logger.error(f"[AST] 会话失败: {error_msg}")
                            yield {
                                "event": "error",
                                "error": error_msg,
                                "error_code": str(response.event),
                                "type": "SessionFailedError"
                            }
                            break

                        elif response.event == Type.SessionFinished:
                            logger.info(f"[AST] 会话正常结束")
                            
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

                        elif response.event == Type.UsageResponse:
                            # 将UsageResponse转换为JSON
                            response_dict = MessageToDict(response)
                            logger.info(f"[AST] 计费信息: {json.dumps(response_dict, indent=2, ensure_ascii=False)}")
                            final_result["tokens"] = response_dict

                        # 处理原文事件
                        elif response.event == 651:  # SourceSubtitleResponse
                            pending_source += response.text
                            logger.info(f"[AST] 原文: {response.text}")
                        elif response.event == 652:  # SourceSubtitleEnd
                            if pending_source:
                                source_buffer.append(pending_source)
                                pending_source = ""
                            logger.info(f"[AST] 原文片段结束")
                        # 处理译文事件
                        elif response.event == 654:  # TranslationSubtitleResponse
                            pending_translation += response.text
                            logger.info(f"[AST] 译文: {response.text}")
                        elif response.event == 655:  # TranslationSubtitleEnd
                            if pending_translation:
                                translation_buffer.append(pending_translation)
                                pending_translation = ""
                            logger.info(f"[AST] 译文片段结束")
                        # 原文字幕（兼容旧版）
                        elif response.text and response.event not in [Type.UsageResponse, 651, 652, 654, 655]:
                            if response.data:
                                # 有音频数据
                                final_result["audio_data"] += response.data
                                logger.info(f"[AST] 收到音频片段: {len(response.data)} bytes")

                            if response.text:
                                # 文本翻译
                                translation_buffer.append(response.text)
                                logger.info(f"[AST] 翻译: {response.text}")

                                yield {
                                    "event": "translation",
                                    "text": response.text,
                                    "sequence": response.response_meta.Sequence
                                }

                except Exception as e:
                    logger.error(f"[AST] 接收消息异常: {e}")
                    raise

                finally:
                    # 确保发送任务完成
                    await sender_task

        except Exception as e:
            elapsed = time.time() - connection_start_time
            error_type = type(e).__name__
            logger.error(f"[AST] ❌ 同声传译失败 (耗时: {elapsed:.2f}秒)")
            logger.error(f"[AST] 错误类型: {error_type}")
            logger.error(f"[AST] 错误信息: {str(e)}")

            # 根据错误类型提供更有用的信息
            if "TimeoutError" in error_type or "timeout" in str(e).lower():
                logger.error(f"[AST] ⏰ 超时错误详情:")
                logger.error(f"[AST]   - 连接阶段超时")
                logger.error(f"[AST]   - 可能原因: 网络延迟、防火墙、DNS解析")
                logger.error(f"[AST]   - 建议: 检查网络连接、尝试VPN、增加超时时间")
            elif "ConnectionRefused" in str(e) or "403" in str(e):
                logger.error(f"[AST] 🔒 连接被拒绝详情:")
                logger.error(f"[AST]   - API认证失败")
                logger.error(f"[AST]   - 可能原因: 凭据无效、权限不足")
                logger.error(f"[AST]   - 建议: 检查API密钥、权限配置")
            elif "HandshakeError" in str(e) or "handshake" in str(e).lower():
                logger.error(f"[AST] 🤝 握手错误详情:")
                logger.error(f"[AST]   - WebSocket握手失败")
                logger.error(f"[AST]   - 可能原因: 协议不匹配、服务器负载高")
                logger.error(f"[AST]   - 建议: 稍后重试、联系服务提供商")

            logger.error(f"[AST] 完整异常信息:", exc_info=True)
            raise
