"""
豆包AST 2.0增强版服务
包含完整的错误处理、重试机制和日志记录
"""
import asyncio
import logging
from typing import Dict, AsyncIterator, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ASTErrorCode(str, Enum):
    """豆包AST错误码"""
    # 成功
    SUCCESS = "20000000"

    # 认证错误
    AUTH_FAILED = "40100001"
    TOKEN_EXPIRED = "40100002"
    APP_NOT_FOUND = "40400001"

    # 请求错误
    INVALID_PARAM = "40000001"
    AUDIO_TOO_SHORT = "40000002"
    UNSUPPORTED_FORMAT = "40000003"

    # 服务错误
    SERVICE_UNAVAILABLE = "50000001"
    INTERNAL_ERROR = "50000002"
    TIMEOUT = "50000003"


class ASTError(Exception):
    """豆包AST错误基类"""
    def __init__(self, code: str, message: str, details: str = ""):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"[{code}] {message}: {details}")


class ASTConnectionError(ASTError):
    """连接错误"""
    pass


class ASTAuthenticationError(ASTError):
    """认证错误"""
    pass


class ASTTranslationError(ASTError):
    """翻译错误"""
    pass


class DoubaoASTEnhanced:
    """豆包AST 2.0增强版服务"""

    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # 秒
    CONNECTION_TIMEOUT = 10.0
    REQUEST_TIMEOUT = 30.0

    def __init__(self, api_id: str, access_token: str):
        """
        初始化增强版豆包AST服务

        Args:
            api_id: API ID
            access_token: Access Token
        """
        self.api_id = api_id
        self.access_token = access_token
        self.ws_url = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"

    async def streaming_translation_with_retry(
        self,
        audio_data: bytes,
        source_language: str = "zh",
        target_language: str = "en",
        format: str = "wav",
        sample_rate: int = 16000
    ) -> AsyncIterator[Dict]:
        """
        带重试机制的流式翻译

        Args:
            audio_data: 音频数据
            source_language: 源语言
            target_language: 目标语言
            format: 音频格式
            sample_rate: 采样率

        Yields:
            翻译结果字典

        Raises:
            ASTError: 翻译失败（已重试3次）
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[AST重试] 第{attempt + 1}/{self.MAX_RETRIES}次尝试")

                # 导入protobuf模块
                import sys
                from pathlib import Path
                protobuf_path = Path(__file__).parent / "protobuf"
                sys.path.insert(0, str(protobuf_path))
                from base.plugins.llm.services.protobuf import doubao_ast_pb2
                import websockets

                # 构建认证Header
                headers = {
                    "X-Api-App-Key": self.api_id,
                    "X-Api-Access-Key": self.access_token,
                    "X-Api-Resource-Id": "volc.service_type.10053"
                }

                # 建立WebSocket连接（带超时）
                async with asyncio.timeout(self.CONNECTION_TIMEOUT):
                    ws = await websockets.connect(
                        self.ws_url,
                        additional_headers=headers
                    )

                try:
                    # 发送StartSession
                    session_id = str(__import__("uuid").uuid4())
                    start_session = doubao_ast_pb2.StartSessionRequest()
                    start_session.request_meta.session_id = session_id
                    start_session.event = 100
                    start_session.user.uid = "user_001"
                    start_session.user.did = "device_001"
                    start_session.user.platform = "Linux"
                    start_session.user.sdk_version = "1.0.0"
                    start_session.request.mode = "s2s"
                    start_session.request.source_language = source_language
                    start_session.request.target_language = target_language
                    start_session.request.service_name = "translate"
                    start_session.source_audio.format = "wav"
                    start_session.source_audio.codec = "raw"
                    start_session.source_audio.rate = 16000
                    start_session.source_audio.bits = 16
                    start_session.source_audio.channel = 1
                    start_session.target_audio.format = "pcm"
                    start_session.target_audio.rate = 24000

                    await ws.send(start_session.SerializeToString())
                    logger.info(f"[AST] 发送StartSession")

                    # 等待SessionStarted响应
                    response_data = await asyncio.wait_for(
                        ws.recv(),
                        timeout=self.REQUEST_TIMEOUT
                    )

                    response = doubao_ast_pb2.SessionStartedResponse()
                    response.ParseFromString(response_data)

                    if response.response_meta.status_code != ASTErrorCode.SUCCESS:
                        error_code = str(response.response_meta.status_code)
                        error_msg = response.response_meta.message or "未知错误"

                        # 认证错误不重试
                        if error_code.startswith("401"):
                            raise ASTAuthenticationError(error_code, error_msg)

                        raise ASTError(error_code, error_msg)

                    logger.info(f"[AST] 会话已建立")

                    # 发送音频数据
                    chunk_size = 2560  # 80ms
                    total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                    for i in range(0, len(audio_data), chunk_size):
                        chunk = audio_data[i:i + chunk_size]

                        task_request = doubao_ast_pb2.TaskRequest()
                        task_request.event = 200
                        task_request.source_audio.data = chunk

                        await ws.send(task_request.SerializeToString())

                        if (i // chunk_size + 1) % 10 == 0:
                            logger.info(f"[AST] 已发送 {i // chunk_size + 1}/{total_chunks} 块")

                        await asyncio.sleep(0.01)

                    # 发送FinishSession
                    finish_session = doubao_ast_pb2.FinishSessionRequest()
                    finish_session.event = 102
                    await ws.send(finish_session.SerializeToString())
                    logger.info(f"[AST] 发送FinishSession")

                    # 接收翻译结果
                    final_result = {
                        "session_id": session_id,
                        "source_text": "",
                        "translation_text": "",
                        "source_segments": [],
                        "translation_segments": []
                    }

                    async for response_data in ws:
                        response_types = [
                            (doubao_ast_pb2.SourceSubtitleResponse, 651),
                            (doubao_ast_pb2.TranslationSubtitleResponse, 654),
                            (doubao_ast_pb2.TTSResponse, 352),
                            (doubao_ast_pb2.UsageResponse, 154),
                            (doubao_ast_pb2.SessionFinishedResponse, 152),
                            (doubao_ast_pb2.SessionFailedResponse, 153),
                        ]

                        for resp_type, expected_event in response_types:
                            try:
                                response = resp_type()
                                response.ParseFromString(response_data)

                                if hasattr(response, 'event') and response.event == expected_event:
                                    # 处理原文
                                    if expected_event == 651:
                                        text = response.text if hasattr(response, 'text') else ""
                                        final_result["source_segments"].append(text)
                                        yield {
                                            "event": "source_subtitle",
                                            "text": text
                                        }

                                    # 处理译文
                                    elif expected_event == 654:
                                        text = response.text if hasattr(response, 'text') else ""
                                        final_result["translation_segments"].append(text)
                                        yield {
                                            "event": "translation_subtitle",
                                            "text": text
                                        }

                                    # 处理TTS
                                    elif expected_event == 352:
                                        data = response.data if hasattr(response, 'data') else b""
                                        yield {
                                            "event": "tts_audio",
                                            "data": data
                                        }

                                    # 会话结束
                                    elif expected_event == 152:
                                        final_result["source_text"] = " ".join(final_result["source_segments"])
                                        final_result["translation_text"] = " ".join(final_result["translation_segments"])
                                        yield {
                                            "event": "session_finished",
                                            "result": final_result
                                        }
                                        return  # 成功完成

                                    # 会话失败
                                    elif expected_event == 153:
                                        error_msg = response.response_meta.message if hasattr(response, 'response_meta') else "未知错误"
                                        raise ASTTranslationError(
                                            str(response.response_meta.status_code) if hasattr(response, 'response_meta') else "50000002",
                                            error_msg
                                        )

                                    break
                            except:
                                continue

                    # 如果正常退出循环，说明成功
                    logger.info(f"[AST] 翻译完成")
                    return

                finally:
                    await ws.close()

            except asyncio.TimeoutError:
                last_error = ASTConnectionError(
                    ASTErrorCode.TIMEOUT,
                    "连接超时",
                    f"attempt {attempt + 1}"
                )
                logger.warning(f"[AST重试] 超时: {last_error}")

            except websockets.exceptions.ConnectionClosed as e:
                last_error = ASTConnectionError(
                    ASTErrorCode.SERVICE_UNAVAILABLE,
                    "连接关闭",
                    str(e)
                )
                logger.warning(f"[AST重试] 连接关闭: {last_error}")

            except ASTAuthenticationError:
                # 认证错误不重试
                raise

            except ASTError:
                # 其他AST错误不重试
                raise

            except Exception as e:
                last_error = ASTError(
                    ASTErrorCode.INTERNAL_ERROR,
                    "未知错误",
                    str(e)
                )
                logger.error(f"[AST重试] 未知错误: {e}", exc_info=True)

            # 如果不是最后一次尝试，等待后重试
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAY * (2 ** attempt))  # 指数退避

        # 所有重试都失败
        raise last_error


# 导出
__all__ = [
    "DoubaoASTEnhanced",
    "ASTErrorCode",
    "ASTError",
    "ASTConnectionError",
    "ASTAuthenticationError",
    "ASTTranslationError"
]
