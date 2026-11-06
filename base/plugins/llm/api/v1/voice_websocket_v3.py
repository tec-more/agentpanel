"""
真正的实时语音翻译 - WebSocket双向通信
带缓冲机制的边收边译版本，模拟真正的实时翻译
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import logging
import json
import uuid
import asyncio
import websockets
from websockets import Headers
from pathlib import Path
import time

from base.common.security import get_current_user_id_ws
# 从统一的使用记录表导入
from base.plugins.llm.models.usage import LLMUsageRecord
from base.plugins.llm.services.voice_helper import VoiceServiceHelper

logger = logging.getLogger(__name__)

voice_websocket_v3_router = APIRouter(
    prefix="/voice",
    tags=["语音服务-WebSocket-V3-缓冲优化"],
)


@voice_websocket_v3_router.websocket("/translation/streaming/v3")
async def websocket_translation_v3(
    websocket: WebSocket,
    provider_id: int = Query(..., description="厂商ID"),
    token: Optional[str] = Query(None, description="认证token")
):
    """
    真正的实时语音翻译 - 带缓冲优化

    关键优化：
    1. 音频缓冲机制 - 累积200-500ms的音频再发送
    2. 定时发送策略 - 每300ms发送一次缓冲的音频
    3. 实时返回翻译 - 收到翻译立即返回客户端

    工作流程：
    1. 客户端发送start
    2. 服务器连接豆包AST
    3. 【循环】:
       - 接收音频块 → 放入缓冲区
       - 每300ms发送一次缓冲区内容给豆包
       - 收到豆包翻译 → 立即返回客户端
    4. 客户端发送end → 完成翻译

    预期延迟：200-500ms
    """
    # #logger.info(f"[实时翻译V3] ========== 新连接 ==========")

    await websocket.accept()
    # #logger.info(f"[实时翻译V3] ✅ WebSocket已accept")

    session_id = None
    record = None
    config = {}
    final_result = {}  # 存储最终翻译结果
    final_result_lock = asyncio.Lock()  # 用于保护final_result的锁
    usage_info = {}  # 存储token使用情况

    # 豆包WebSocket连接
    doubao_ws = None
    doubao_connected = False

    # 音频缓冲
    audio_buffer = bytearray()
    last_send_time = None
    buffer_lock = asyncio.Lock()

    # 原文和译文片段
    source_segments = []  # 原文片段
    translation_segments = []  # 译文片段

    # 控制标志
    is_running = False
    stop_event = asyncio.Event()
    final_result_ready = asyncio.Event()  # 用于通知final_result已准备好

    # 异步任务
    sender_task = None
    receiver_task = None
    buffer_flush_task = None

    try:
        # 验证用户
        user_id = await get_current_user_id_ws(token)
        if not user_id:
            try:
                await websocket.send_json({"type": "error", "message": "未授权"})
            except (WebSocketDisconnect, RuntimeError):
                pass
            await websocket.close(code=1008, reason="Unauthorized")
            return

        #logger.info(f"[实时翻译V3] ✅ 用户验证成功: {user_id}")

        while True:
            message = await websocket.receive()

            # 处理控制消息
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type")

                    #logger.info(f"[实时翻译V3] 收到控制消息: {msg_type}")

                    if msg_type == "start":
                        # 如果已有记录，先更新状态
                        if record and record.status == "processing":
                            from datetime import datetime
                            import pytz
                            record.status = "failed"
                            record.end_time = datetime.now(pytz.UTC)
                            await record.save()
                            logger.warning(f"[实时翻译V3] ⚠️  检测到未完成的旧记录，已标记为失败")

                        # 创建会话
                        session_id = f"rt_v3_{uuid.uuid4().hex[:16]}"
                        config = {
                            "format": data.get("format", "wav"),
                            "sample_rate": data.get("sample_rate", 16000),
                            "source_language": data.get("source_language", "zh"),
                            "target_language": data.get("target_language", "en"),
                        }

                        #logger.info(f"[实时翻译V3] ========== 🎬 会话开始 ==========")
                        #logger.info(f"[实时翻译V3] SessionID: {session_id}")
                        #logger.info(f"[实时翻译V3] 源语言: {config['source_language']}")
                        #logger.info(f"[实时翻译V3] 目标语言: {config['target_language']}")
                        #logger.info(f"[实时翻译V3] 音频格式: {config['format']}")
                        #logger.info(f"[实时翻译V3] 采样率: {config['sample_rate']} Hz")
                        #logger.info(f"[实时翻译V3] ========================================")

                        # 创建数据库记录
                        from datetime import datetime
                        import pytz
                        from base.plugins.llm.models.usage import LLMUsageRecord
                        record = await LLMUsageRecord.create(
                            record_id=session_id,
                            customer_id=user_id,
                            model_id=provider_id,
                            record_type="voice",
                            audio_file="websocket_v3",
                            audio_format=config["format"],
                            source_language=config["source_language"],
                            target_language=config["target_language"],
                            status="processing",
                            start_time=datetime.now(pytz.UTC) 
                        )




                        #logger.info(f"[实时翻译V3] ✅ 数据库记录已创建")

                        # 连接豆包AST
                        #logger.info(f"[实时翻译V3] ========== 连接豆包AST ==========")

                        try:
                            service = await VoiceServiceHelper.get_voice_service(provider_id)

                            from base.plugins.llm.services.doubao_voice_service import DoubaoVoiceService
                            if not isinstance(service, DoubaoVoiceService):
                                raise ValueError("需要豆包AST服务")

                            # 准备连接参数
                            ws_url = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
                            conn_id = str(uuid.uuid4())

                            # 调试：打印认证信息
                            logger.info(f"[实时翻译V3] 认证信息:")
                            logger.info(f"  api_id: {service.api_id}")
                            logger.info(f"  api_key: {service.api_key[:20]}..." if service.api_key else "  api_key: None")
                            logger.info(f"  access_token: {service.access_token[:20]}..." if service.access_token else "  access_token: None")

                            # 豆包AST 2.0认证方式
                            # 方式1: 使用App Key + Access Token
                            # 方式2: 使用API Key (app_id:secret格式)
                            
                            # 尝试使用API Key进行认证
                            api_key = service.api_key
                            if ':' in api_key:
                                # API Key格式: app_id:secret
                                app_id, secret = api_key.split(':', 1)
                                headers = Headers({
                                    "X-Api-App-Key": app_id,
                                    "X-Api-Access-Key": secret,
                                    "X-Api-Resource-Id": "volc.service_type.10053",
                                    "X-Api-Connect-Id": conn_id
                                })
                                logger.info(f"[实时翻译V3] 使用API Key认证方式 (app_id:secret)")
                            else:
                                # 使用Access Token认证方式
                                headers = Headers({
                                    "X-Api-App-Key": service.api_id or service.api_key,
                                    "X-Api-Access-Key": service.access_token or service.api_key,
                                    "X-Api-Resource-Id": "volc.service_type.10053",
                                    "X-Api-Connect-Id": conn_id
                                })
                                logger.info(f"[实时翻译V3] 使用Access Token认证方式")

                            logger.info(f"[实时翻译V3] 请求头:")
                            logger.info(f"  X-Api-App-Key: {headers.get('X-Api-App-Key', 'Not Set')}")
                            logger.info(f"  X-Api-Access-Key: {headers.get('X-Api-Access-Key', 'Not Set')[:20]}..." if headers.get('X-Api-Access-Key') else "  X-Api-Access-Key: Not Set")
                            logger.info(f"  X-Api-Resource-Id: {headers.get('X-Api-Resource-Id')}")

                            logger.info(f"[实时翻译V3] 连接到豆包AST...")

                            # 连接豆包AST
                            doubao_ws = await websockets.connect(
                                ws_url,
                                additional_headers=headers,
                                max_size=1000000000,
                                ping_interval=None,
                                close_timeout=30,
                                open_timeout=60  # 增加连接超时时间到60秒
                            )

                            doubao_connected = True
                            #logger.info(f"[实时翻译V3] ✅ 豆包AST连接成功")

                            # 发送StartSession
                            from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest, TranslateResponse
                            from python_protogen.common.events_pb2 import Type

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
                            request_data.request.source_language = config["source_language"]
                            request_data.request.target_language = config["target_language"]

                            await doubao_ws.send(request_data.SerializeToString())

                            # 打印翻译配置信息
                            #logger.info(f"[实时翻译V3] ========== 🌐 翻译配置 ==========")
                            #logger.info(f"[实时翻译V3] 源语言 (source_language): {config['source_language']}")
                            #logger.info(f"[实时翻译V3] 目标语言 (target_language): {config['target_language']}")
                            #logger.info(f"[实时翻译V3] 翻译模式 (mode): s2s (Speech-to-Speech)")
                            #logger.info(f"[实时翻译V3] =============================")
                            #logger.info(f"[实时翻译V3] ✅ StartSession已发送")

                            # 等待SessionStarted
                            response_data = await doubao_ws.recv()
                            Response_data = TranslateResponse()
                            Response_data.ParseFromString(response_data)

                            if Response_data.event != Type.SessionStarted:
                                error_msg = f"会话建立失败: {Response_data.response_meta.Message}"
                                logger.error(f"[实时翻译V3] {error_msg}")
                                try:
                                    await websocket.send_json({"type": "error", "message": error_msg})
                                except (WebSocketDisconnect, RuntimeError):
                                    pass
                                break

                            #logger.info(f"[实时翻译V3] ✅ 会话已建立")

                            # 初始化缓冲
                            audio_buffer.clear()
                            last_send_time = time.time()
                            is_running = True

                            # 启动定时刷新任务
                            async def flush_buffer_periodically():
                                """每500ms发送一次缓冲的音频"""
                                try:
                                    flush_interval = 0.3  # 300ms
                                    min_buffer_size = 3200  # 最小3200字节

                                    while is_running and not stop_event.is_set():
                                        await asyncio.sleep(flush_interval)

                                        async with buffer_lock:
                                            if len(audio_buffer) >= min_buffer_size:
                                                # 发送缓冲的音频
                                                chunk = bytes(audio_buffer)
                                                audio_buffer.clear()

                                                # 计算音频时长
                                                duration_ms = len(chunk) / 2 / 16  # (字节数 / 2字节/采样) / 16kHz * 1000
                                                duration_s = duration_ms / 1000

                                                #logger.info(f"[实时翻译V3-刷新] ========== 发送缓冲音频 ==========")
                                                #logger.info(f"[实时翻译V3-刷新] 大小: {len(chunk)} bytes")
                                                #logger.info(f"[实时翻译V3-刷新] 时长: {duration_s:.2f} 秒 ({duration_ms:.0f} 毫秒)")
                                                #logger.info(f"[实时翻译V3-刷新] 采样率: 16000 Hz, 16bit, 单声道")

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
                                                request_data.request.source_language = config["source_language"]
                                                request_data.request.target_language = config["target_language"]

                                                serialized = request_data.SerializeToString()
                                                await doubao_ws.send(serialized)
                                                #logger.info(f"[实时翻译V3-刷新] ✅ 已发送到豆包AST ({len(serialized)} bytes)")
                                                #logger.info(f"[实时翻译V3-刷新] ===============================")

                                except Exception as e:
                                    logger.error(f"[实时翻译V3-刷新] 异常: {e}", exc_info=True)

                            buffer_flush_task = asyncio.create_task(flush_buffer_periodically())

                            # 启动翻译接收任务
                            async def receive_translation_from_doubao():
                                """接收豆包AST的翻译结果"""
                                nonlocal final_result  # 声明使用外部变量
                                try:
                                    # 使用外部的source_segments和translation_segments
                                    response_count = 0

                                    #logger.info(f"[实时翻译V3-接收] ========== 开始接收 ==========")

                                    while is_running and not stop_event.is_set():
                                        try:
                                            response_data = await asyncio.wait_for(
                                                doubao_ws.recv(),
                                                timeout=1.0
                                            )
                                        except asyncio.TimeoutError:
                                            continue

                                        response_count += 1
                                        Response_data = TranslateResponse()
                                        Response_data.ParseFromString(response_data)

                                        event_type = Response_data.event
                                        #logger.info(f"[实时翻译V3-接收] 响应#{response_count}: Event={event_type} ({Type.Name(event_type)})")

                                        # 会话失败
                                        if event_type == 153:  # SessionFailed
                                            error_msg = Response_data.response_meta.Message
                                            logger.error(f"[实时翻译V3] ❌ 会话失败: {error_msg}")
                                            try:
                                                await websocket.send_json({"type": "error", "message": error_msg})
                                            except (WebSocketDisconnect, RuntimeError):
                                                pass
                                            break

                                        # 会话完成
                                        if event_type == 152:  # SessionFinished
                                            #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")
                                            #logger.info(f"[实时翻译V3] 🎉 会话完成")
                                            #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")

                                            # 智能合并原文和译文片段，确保标点符号对齐
                                            def smart_join(segments):
                                                result = ""
                                                for seg in segments:
                                                    if not result:
                                                        result = seg
                                                    else:
                                                        # 如果前一个字符是标点符号，直接连接
                                                        if result[-1] in ["，", "。", "！", "？", ",", ".", "!", "?"]:
                                                            result += seg
                                                        # 如果当前片段以标点符号开头，直接连接
                                                        elif seg and seg[0] in ["，", "。", "！", "？", ",", ".", "!", "?"]:
                                                            result += seg
                                                        # 否则添加空格
                                                        else:
                                                            result += " " + seg
                                                return result
                                            
                                            # 更新外部的final_result变量
                                            async with final_result_lock:
                                                final_result.update({
                                                    "session_id": session_id,
                                                    "source_text": smart_join(source_segments),
                                                    "translation_text": smart_join(translation_segments),
                                                    "source_segments": source_segments,
                                                    "translation_segments": translation_segments,
                                                    "tokens": usage_info
                                                })
                                            
                                            # 通知final_result已准备好
                                            final_result_ready.set()

                                            # 打印最终汇总
                                            logger.info(f"[实时翻译V3] ═══════════════════════════════════════")
                                            logger.info(f"[实时翻译V3] 📊 最终翻译汇总")
                                            logger.info(f"[实时翻译V3] ═══════════════════════════════════════")
                                            logger.info(f"[实时翻译V3] 源语言      : {config['source_language']}")
                                            logger.info(f"[实时翻译V3] 目标语言    : {config['target_language']}")
                                            logger.info(f"[实时翻译V3] 原文片段数  : {len(source_segments)}")
                                            logger.info(f"[实时翻译V3] 译文片段数  : {len(translation_segments)}")
                                            logger.info(f"[实时翻译V3] 完整原文    : {smart_join(source_segments)}")
                                            logger.info(f"[实时翻译V3] 完整译文    : {smart_join(translation_segments)}")
                                            logger.info(f"[实时翻译V3] ═══════════════════════════════════════")

                                            try:
                                                await websocket.send_json({
                                                    "type": "session_finished",
                                                    "result": final_result
                                                })
                                            except (WebSocketDisconnect, RuntimeError):
                                                pass
                                            break

                                        # Token使用情况
                                        if event_type == 154:  # UsageResponse
                                            from google.protobuf.json_format import MessageToDict
                                            usage_info.update(MessageToDict(Response_data))
                                            logger.info(f"[实时翻译V3] 📊 Token使用情况: {usage_info}")

                                        # ========== 原文事件 (650-652) ==========
                                        elif event_type == 650:  # SourceSubtitleStart
                                            logger.info(f"[实时翻译V3] ========== 📖 原文开始 ==========")

                                        elif event_type == 651:  # SourceSubtitleResponse
                                            # 原文数据
                                            if hasattr(Response_data, 'text') and Response_data.text:
                                                source_segments.append(Response_data.text)

                                                #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")
                                                #logger.info(f"[实时翻译V3] 📖 原文片段 #{len(source_segments)}")
                                                #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")
                                                #logger.info(f"[实时翻译V3] 源语言    : {config['source_language']}")
                                                #logger.info(f"[实时翻译V3] 原文      : {Response_data.text}")
                                                #logger.info(f"[实时翻译V3] 累积原文  : {' '.join(source_segments)}")
                                                #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")

                                                # 发送给客户端
                                                try:
                                                    await websocket.send_json({
                                                        "type": "source",
                                                        "text": Response_data.text,
                                                        "language": config["source_language"],
                                                        "source_segments": ' '.join(source_segments),
                                                        "segment_index": len(source_segments)
                                                    })
                                                except (WebSocketDisconnect, RuntimeError):
                                                    # WebSocket已关闭，跳过发送
                                                    break

                                        elif event_type == 652:  # SourceSubtitleEnd
                                            logger.info(f"[实时翻译V3] ========== 📖 原文结束 ==========")

                                        # ========== 译文事件 (653-655) ==========
                                        elif event_type == 653:  # TranslationSubtitleStart
                                            logger.info(f"[实时翻译V3] ========== 📝 译文开始 ==========")

                                        elif event_type == 654:  # TranslationSubtitleResponse
                                            # 译文数据
                                            if hasattr(Response_data, 'text') and Response_data.text:
                                                translation_segments.append(Response_data.text)

                                                #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")
                                                #logger.info(f"[实时翻译V3] 📝 译文片段 #{len(translation_segments)}")
                                                #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")
                                                #logger.info(f"[实时翻译V3] 目标语言  : {config['target_language']}")
                                                #logger.info(f"[实时翻译V3] 译文      : {Response_data.text}")
                                                #logger.info(f"[实时翻译V3] 累积译文  : {' '.join(translation_segments)}")
                                                #logger.info(f"[实时翻译V3] ═══════════════════════════════════════")

                                                # 发送给客户端
                                                try:
                                                    await websocket.send_json({
                                                        "type": "translation",
                                                        "text": Response_data.text,
                                                        "language": config["target_language"],
                                                        "translation_segments": ' '.join(translation_segments),
                                                        "segment_index": len(translation_segments)
                                                    })
                                                except (WebSocketDisconnect, RuntimeError):
                                                    # WebSocket已关闭，跳过发送
                                                    break

                                        elif event_type == 655:  # TranslationSubtitleEnd
                                            logger.info(f"[实时翻译V3] ========== 📝 译文结束 ==========")

                                except Exception as e:
                                    logger.error(f"[实时翻译V3-接收] 异常: {e}", exc_info=True)

                            receiver_task = asyncio.create_task(receive_translation_from_doubao())

                            try:
                                await websocket.send_json({
                                    "type": "started",
                                    "session_id": session_id
                                })
                            except (WebSocketDisconnect, RuntimeError):
                                pass

                            #logger.info(f"[实时翻译V3] ✅ 会话已启动，缓冲机制已启用")

                        except Exception as e:
                            logger.error(f"[实时翻译V3] 连接豆包AST失败: {e}", exc_info=True)
                            try:
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"连接翻译服务失败: {str(e)}"
                                })
                            except (WebSocketDisconnect, RuntimeError):
                                pass
                            break

                    elif msg_type == "end":
                        #logger.info(f"[实时翻译V3] ========== 收到end消息 ==========")

                        is_running = False
                        stop_event.set()

                        # 发送剩余的缓冲
                        async with buffer_lock:
                            if len(audio_buffer) > 0:
                                #logger.info(f"[实时翻译V3] 发送剩余缓冲: {len(audio_buffer)} bytes")

                                from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest
                                from python_protogen.common.events_pb2 import Type

                                request_data = TranslateRequest()
                                request_data.request_meta.SessionID = session_id
                                request_data.event = Type.TaskRequest
                                request_data.user.uid = "ast_py_client"
                                request_data.user.did = "ast_py_client"
                                request_data.source_audio.format = "wav"
                                request_data.source_audio.rate = 16000
                                request_data.source_audio.bits = 16
                                request_data.source_audio.channel = 1
                                request_data.source_audio.binary_data = bytes(audio_buffer)
                                request_data.target_audio.format = "ogg_opus"
                                request_data.target_audio.rate = 24000
                                request_data.request.mode = "s2s"
                                request_data.request.source_language = config["source_language"]
                                request_data.request.target_language = config["target_language"]

                                await doubao_ws.send(request_data.SerializeToString())
                                audio_buffer.clear()

                        # 发送FinishSession
                        from python_protogen.products.understanding.ast.ast_service_pb2 import TranslateRequest
                        from python_protogen.common.events_pb2 import Type

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

                        await doubao_ws.send(request_data.SerializeToString())
                        #logger.info(f"[实时翻译V3] ✅ FinishSession已发送")

                        # 等待任务完成
                        if buffer_flush_task:
                            await buffer_flush_task
                        if receiver_task:
                            await receiver_task

                        # 关闭豆包连接
                        if doubao_ws:
                            await doubao_ws.close()
                            doubao_connected = False

                        # 等待final_result准备好（最多等待5秒）
                        try:
                            await asyncio.wait_for(final_result_ready.wait(), timeout=5.0)
                            logger.info(f"[实时翻译V3] ✅ final_result已准备好")
                        except asyncio.TimeoutError:
                            logger.warning(f"[实时翻译V3] ⚠️ 等待final_result超时，可能未收到SessionFinished事件")
                            # 如果没有收到SessionFinished事件，使用已有的source_segments和translation_segments
                            if source_segments or translation_segments:
                                logger.info(f"[实时翻译V3] 使用已有的source_segments和translation_segments")
                                # 智能合并原文和译文片段，确保标点符号对齐
                                def smart_join(segments):
                                    result = ""
                                    for seg in segments:
                                        if not result:
                                            result = seg
                                        else:
                                            # 如果前一个字符是标点符号，直接连接
                                            if result[-1] in ["，", "。", "！", "？", ",", ".", "!", "?"]:
                                                result += seg
                                            # 如果当前片段以标点符号开头，直接连接
                                            elif seg and seg[0] in ["，", "。", "！", "？", ",", ".", "!", "?"]:
                                                result += seg
                                            # 否则添加空格
                                            else:
                                                result += " " + seg
                                    return result
                                
                                # 更新final_result
                                async with final_result_lock:
                                    final_result.update({
                                        "session_id": session_id,
                                        "source_text": smart_join(source_segments),
                                        "translation_text": smart_join(translation_segments),
                                        "source_segments": source_segments,
                                        "translation_segments": translation_segments,
                                        "tokens": usage_info
                                    })
                                logger.info(f"[实时翻译V3] 已更新final_result: {final_result}")

                        # 更新数据库
                        if record:
                            from datetime import datetime
                            import pytz
                            from base.plugins.llm.services.cost_calculator import HumorousChatCostCalculator
                            
                            # 计算会话时长
                            duration_seconds = 0
                            if record.start_time:
                                duration_seconds = int((datetime.now(pytz.UTC) - record.start_time).total_seconds())
                            
                            # 计算费用
                            total_cost = 0
                            source_text = ""
                            translation_text = ""
                            total_tokens = 0
                            
                            logger.info(f"[实时翻译V3] ========== 开始写入数据库 ==========")
                            logger.info(f"[实时翻译V3] record_id: {record.record_id}")
                            
                            # 使用锁保护读取final_result
                            async with final_result_lock:
                                logger.info(f"[实时翻译V3] final_result: {final_result}")
                                
                                if final_result:
                                    source_text = final_result.get("source_text", "")
                                    translation_text = final_result.get("translation_text", "")
                                    tokens_info = final_result.get("tokens", {})
                                    
                                    logger.info(f"[实时翻译V3] final_result中的tokens: {tokens_info}")
                                    logger.info(f"[实时翻译V3] usage_info: {usage_info}")
                                    
                                    # 如果final_result中没有tokens，使用usage_info
                                    if not tokens_info and usage_info:
                                        tokens_info = usage_info
                                        logger.info(f"[实时翻译V3] 使用usage_info作为tokens_info: {usage_info}")
                                    
                                    # 计算token数 - 从billing.items中提取
                                    def calculate_tokens(info):
                                        """计算token数 - 从豆包AST的billing格式提取"""
                                        if not info:
                                            return 0
                                        
                                        total = 0
                                        
                                        # 豆包AST格式: responseMeta.billing.items
                                        if isinstance(info, dict):
                                            # 检查是否是billing结构
                                            if 'billing' in info and isinstance(info['billing'], dict):
                                                billing = info['billing']
                                                if 'items' in billing and isinstance(billing['items'], list):
                                                    for item in billing['items']:
                                                        if isinstance(item, dict) and 'quantity' in item:
                                                            quantity = item['quantity']
                                                            unit = item.get('unit', '')
                                                            if isinstance(quantity, (int, float)):
                                                                total += quantity
                                                                logger.info(f"[实时翻译V3] Token项目 {unit}: {quantity}")
                                            
                                            # 递归检查其他字段
                                            for key, value in info.items():
                                                if isinstance(value, dict):
                                                    total += calculate_tokens(value)
                                                elif isinstance(value, list):
                                                    for item in value:
                                                        if isinstance(item, dict):
                                                            total += calculate_tokens(item)
                                        
                                        return total
                                    
                                    total_tokens = calculate_tokens(tokens_info)
                                    logger.info(f"[实时翻译V3] 计算的token数: {total_tokens}")
                                    
                                    logger.info(f"[实时翻译V3] source_text (从final_result获取): '{source_text}'")
                                    logger.info(f"[实时翻译V3] translation_text (从final_result获取): '{translation_text}'")
                                    logger.info(f"[实时翻译V3] source_text长度: {len(source_text)}")
                                    logger.info(f"[实时翻译V3] translation_text长度: {len(translation_text)}")
                                    logger.info(f"[实时翻译V3] tokens_info: {tokens_info}")
                                    logger.info(f"[实时翻译V3] total_tokens: {total_tokens}")
                                else:
                                    logger.warning(f"[实时翻译V3] final_result为空，无法写入input_text和output_text")
                                    logger.warning(f"[实时翻译V3] record.input_text将保持为: '{record.input_text}'")
                                    logger.warning(f"[实时翻译V3] record.output_text将保持为: '{record.output_text}'")
                            
                            if source_text or translation_text:
                                # 计算ASR费用（根据音频时长）
                                asr_cost = HumorousChatCostCalculator.calculate_asr_cost(
                                    duration_seconds=duration_seconds,
                                    provider="doubao"
                                )
                                
                                # 计算LLM费用（根据翻译文本）
                                llm_cost = HumorousChatCostCalculator.calculate_llm_cost(
                                    input_text=source_text,
                                    output_text=translation_text,
                                    model="doubao_pro"
                                )
                                
                                total_cost = float(asr_cost) + float(llm_cost)
                                
                                logger.info(f"[实时翻译V3] 💰 费用计算:")
                                logger.info(f"  音频时长: {duration_seconds}秒")
                                logger.info(f"  ASR费用: ¥{float(asr_cost):.4f}")
                                logger.info(f"  LLM费用: ¥{float(llm_cost):.4f}")
                                logger.info(f"  总费用: ¥{total_cost:.4f}")
                            
                            # 更新记录
                            record.status = "completed"
                            record.end_time = datetime.now(pytz.UTC)
                            record.audio_duration = duration_seconds  # 添加音频时长
                            record.tokens = total_tokens
                            record.cost = total_cost
                            record.input_text = source_text
                            record.output_text = translation_text
                            
                            logger.info(f"[实时翻译V3] 准备保存记录...")
                            logger.info(f"[实时翻译V3] record.status: {record.status}")
                            logger.info(f"[实时翻译V3] record.end_time: {record.end_time}")
                            logger.info(f"[实时翻译V3] record.audio_duration: {record.audio_duration}")
                            logger.info(f"[实时翻译V3] record.input_text: '{record.input_text}'")
                            logger.info(f"[实时翻译V3] record.output_text: '{record.output_text}'")
                            
                            await record.save()
                            
                            logger.info(f"[实时翻译V3] 记录已保存")
                            logger.info(f"[实时翻译V3] record_id: {record.record_id}")
                            logger.info(f"[实时翻译V3] record.input_text (保存后): '{record.input_text}'")
                            logger.info(f"[实时翻译V3] record.output_text (保存后): '{record.output_text}'")
                            logger.info(f"[实时翻译V3] ======================================")
                            
                            # 更新API密钥使用量
                            if total_tokens > 0:
                                await VoiceServiceHelper.update_voice_usage(
                                    service,
                                    tokens=int(total_tokens)
                                )

                        try:
                            await websocket.send_json({
                                "type": "ended",
                                "session_id": session_id
                            })
                        except (WebSocketDisconnect, RuntimeError):
                            # WebSocket已关闭，跳过发送
                            pass

                        #logger.info(f"[实时翻译V3] ✅ 会话正常结束")
                        break

                    else:
                        try:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"未知消息类型: {msg_type}"
                            })
                        except (WebSocketDisconnect, RuntimeError):
                            pass

                except json.JSONDecodeError as e:
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"JSON解析错误: {str(e)}"
                        })
                    except (WebSocketDisconnect, RuntimeError):
                        pass

            # 处理音频数据 - 放入缓冲区
            elif "bytes" in message:
                audio_chunk = message["bytes"]

                #logger.info(f"[实时翻译V3] ========== 📥 收到音频块 ==========")
                #logger.info(f"[实时翻译V3] 原始大小: {len(audio_chunk)} bytes")
                #logger.info(f"[实时翻译V3] 是否WAV: {'是' if len(audio_chunk) >= 4 and audio_chunk[:4] == b'RIFF' else '否'}")

                # 提取PCM（如果是WAV格式）
                pcm_data = audio_chunk
                try:
                    if len(audio_chunk) >= 4 and audio_chunk[:4] == b'RIFF':
                        import io
                        import wave
                        audio_file_obj = io.BytesIO(audio_chunk)
                        with wave.open(audio_file_obj, 'rb') as wf:
                            pcm_data = wf.readframes(wf.getnframes())
                        #logger.info(f"[实时翻译V3] 提取PCM: {len(audio_chunk)} -> {len(pcm_data)} bytes")
                        #logger.info(f"[实时翻译V3] WAV头部: {len(audio_chunk) - len(pcm_data)} bytes")
                    # else:
                    #     logger.info(f"[实时翻译V3] 纯PCM数据")
                except Exception as e:
                    logger.warning(f"[实时翻译V3] PCM提取失败: {e}")

                # 计算音频时长
                duration_ms = len(pcm_data) / 2 / 16  # 毫秒
                #logger.info(f"[实时翻译V3] 音频时长: {duration_ms:.0f} 毫秒 ({duration_ms/1000:.2f} 秒)")

                # 放入缓冲区
                if doubao_connected:
                    async with buffer_lock:
                        before_size = len(audio_buffer)
                        audio_buffer.extend(pcm_data)
                        after_size = len(audio_buffer)
                        added_size = after_size - before_size

                        #logger.info(f"[实时翻译V3] ========== 缓冲区状态 ==========")
                        #logger.info(f"[实时翻译V3] 添加: {added_size} bytes")
                        #logger.info(f"[实时翻译V3] 当前缓冲: {after_size} bytes")
                        #logger.info(f"[实时翻译V3] 缓冲时长: {after_size / 2 / 16 / 1000:.2f} 秒")
                        #logger.info(f"[实时翻译V3] 距离最小缓冲: {max(0, 3200 - after_size)} bytes")
                        #logger.info(f"[实时翻译V3] =============================")
                else:
                    logger.warning(f"[实时翻译V3] ⚠️  豆包未连接，丢弃音频块")

    except WebSocketDisconnect:
        logger.info(f"[实时翻译V3] 客户端断开连接")
        is_running = False
        stop_event.set()

        # 清理资源
        if buffer_flush_task:
            buffer_flush_task.cancel()
        if receiver_task:
            receiver_task.cancel()

        if doubao_ws:
            await doubao_ws.close()

        # 更新当前记录
        if record:
            from datetime import datetime
            import pytz
            from base.plugins.llm.services.cost_calculator import HumorousChatCostCalculator
            
            if record.status == "processing":
                # 计算会话时长
                duration_seconds = 0
                if record.start_time:
                    duration_seconds = int((datetime.now(pytz.UTC) - record.start_time).total_seconds())
                
                # 计算费用（失败的会话，如果有部分结果则计算部分费用）
                total_cost = 0
                source_text = ""
                translation_text = ""
                total_tokens = 0
                
                if final_result:
                    source_text = final_result.get("source_text", "")
                    translation_text = final_result.get("translation_text", "")
                    tokens_info = final_result.get("tokens", {})
                    
                    logger.info(f"[实时翻译V3] final_result中的tokens: {tokens_info}")
                    logger.info(f"[实时翻译V3] usage_info: {usage_info}")
                    
                    # 如果final_result中没有tokens，使用usage_info
                    if not tokens_info and usage_info:
                        tokens_info = usage_info
                        logger.info(f"[实时翻译V3] 使用usage_info作为tokens_info: {usage_info}")
                    
                    # 计算token数 - 从billing.items中提取
                    def calculate_tokens(info):
                        """计算token数 - 从豆包AST的billing格式提取"""
                        if not info:
                            return 0
                        
                        total = 0
                        
                        # 豆包AST格式: responseMeta.billing.items
                        if isinstance(info, dict):
                            # 检查是否是billing结构
                            if 'billing' in info and isinstance(info['billing'], dict):
                                billing = info['billing']
                                if 'items' in billing and isinstance(billing['items'], list):
                                    for item in billing['items']:
                                        if isinstance(item, dict) and 'quantity' in item:
                                            quantity = item['quantity']
                                            unit = item.get('unit', '')
                                            if isinstance(quantity, (int, float)):
                                                total += quantity
                                                logger.info(f"[实时翻译V3] Token项目 {unit}: {quantity}")
                            
                            # 递归检查其他字段
                            for key, value in info.items():
                                if isinstance(value, dict):
                                    total += calculate_tokens(value)
                                elif isinstance(value, list):
                                    for item in value:
                                        if isinstance(item, dict):
                                            total += calculate_tokens(item)
                        
                        return total
                    
                    total_tokens = calculate_tokens(tokens_info)
                    logger.info(f"[实时翻译V3] 计算的token数: {total_tokens}")
                    
                    # 计算ASR费用（根据音频时长）
                    asr_cost = HumorousChatCostCalculator.calculate_asr_cost(
                        duration_seconds=duration_seconds,
                        provider="doubao"
                    )
                    
                    # 计算LLM费用（根据翻译文本）
                    llm_cost = HumorousChatCostCalculator.calculate_llm_cost(
                        input_text=source_text,
                        output_text=translation_text,
                        model="doubao_pro"
                    )
                    
                    total_cost = float(asr_cost) + float(llm_cost)
                    
                    logger.info(f"[实时翻译V3] 💰 失败会话的部分费用:")
                    logger.info(f"  音频时长: {duration_seconds}秒")
                    logger.info(f"  ASR费用: ¥{float(asr_cost):.4f}")
                    logger.info(f"  LLM费用: ¥{float(llm_cost):.4f}")
                    logger.info(f"  总费用: ¥{total_cost:.4f}")
                    logger.info(f"  tokens_info: {tokens_info}")
                    logger.info(f"  total_tokens: {total_tokens}")
                
                record.status = "failed"
                record.end_time = datetime.now(pytz.UTC)
                record.audio_duration = duration_seconds  # 添加音频时长
                record.tokens = total_tokens
                record.cost = total_cost
                record.input_text = source_text
                record.output_text = translation_text
                await record.save()
                logger.info(f"[实时翻译V3] 记录已标记为失败: {record.record_id}")

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
                logger.info(f"[实时翻译V3] 清理残留记录: {rec.record_id}")

    except Exception as e:
        logger.error(f"[实时翻译V3] 异常: {e}", exc_info=True)

        try:
            await websocket.send_json({
                "type": "error",
                "message": f"服务器错误: {str(e)}"
            })
        except:
            pass

        is_running = False
        stop_event.set()

        # 清理资源
        if buffer_flush_task:
            buffer_flush_task.cancel()
        if receiver_task:
            receiver_task.cancel()

        if doubao_ws:
            await doubao_ws.close()

        if record:
            try:
                from datetime import datetime
                import pytz
                record.status = "failed"
                record.error_message = str(e)
                record.end_time = datetime.now(pytz.UTC) 
                await record.save()
            except:
                pass

    finally:
        logger.info(f"[实时翻译V3] ========== 会话结束 ==========")


__all__ = ["voice_websocket_v3_router"]
