"""
豆包语音服务 - 完整实现
"""
import json
import httpx
import asyncio
import websockets
import logging
from typing import AsyncIterator, Dict, Optional, BinaryIO
from pathlib import Path

logger = logging.getLogger(__name__)


class DoubaoVoiceService:
    """豆包语音服务类 - 完整版"""

    def __init__(self, api_key: str, endpoint_url: str = "https://openspeech.bytedance.com", api_secret: str = None, **kwargs):
        """
        初始化豆包语音服务

        Args:
            api_key: API密钥
            endpoint_url: API端点URL
            api_secret: API密钥（保留参数以兼容其他服务，豆包不使用此参数）
            **kwargs: 其他兼容性参数，包括 api_id, access_token
        """
        self.api_key = api_key
        # 处理 endpoint_url 为 None 的情况
        if endpoint_url:
            self.endpoint_url = endpoint_url.rstrip('/')
        else:
            self.endpoint_url = "https://openspeech.bytedance.com"
            logger.warning("endpoint_url 为空，使用豆包默认端点")

        self.app_id = self._extract_app_id(api_key)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # api_secret 参数被接受但不使用（豆包只需要 api_key）

        # 保存额外的认证信息（用于AST 2.0等服务）
        self.api_id = kwargs.get('api_id', '')
        self.access_token = kwargs.get('access_token', '')

    def _extract_app_id(self, api_key: str) -> str:
        """从API Key提取App ID"""
        # 豆包的API Key格式通常是 app_id:secret
        if ':' in api_key:
            return api_key.split(':')[0]
        return api_key

    # ========== 1. 流式语音识别（ASR实时） ==========

    async def streaming_asr(self, audio_data: bytes, format: str = "wav",
                            sample_rate: int = 16000, language: str = "zh") -> AsyncIterator[Dict]:
        """
        流式语音识别（实时）

        Args:
            audio_data: 音频数据
            format: 音频格式（wav/mp3/opus等）
            sample_rate: 采样率（16000）
            language: 语言（zh/en等）

        Yields:
            识别结果片段
        """
        ws_url = "wss://openspeech.bytedance.com/api/v2/asr"

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.api_key,
                "cluster": "volcano_tob"
            },
            "user": {
                "uid": "user_001"
            },
            "audio": {
                "format": format,
                "sample_rate": sample_rate,
                "language": language,
                "bits": 16,
                "channel": 1
            },
            "request": {
                "reqid": f"asr_{asyncio.get_event_loop().time()}",
                "nbest": 1,
                "enable_punctuation": True,
                "enable_itn": False
            }
        }

        try:
            async with websockets.connect(ws_url) as ws:
                # 发送配置
                await ws.send(json.dumps(payload))

                # 发送音频数据
                await ws.send(audio_data)

                # 接收结果
                while True:
                    response = await ws.recv()
                    result = json.loads(response)

                    if result.get("result") == "success":
                        yield result
                    elif result.get("is_final"):
                        break
                    elif result.get("error_code"):
                        raise Exception(f"ASR错误: {result.get('message')}")

        except Exception as e:
            logger.error(f"流式ASR失败: {str(e)}")
            raise

    # ========== 2. 录音文件识别（ASR文件） ==========

    async def file_asr(self, audio_file: str, format: str = "wav",
                      sample_rate: int = 16000, language: str = "zh") -> Dict:
        """
        录音文件识别

        Args:
            audio_file: 音频文件路径或URL
            format: 音频格式
            sample_rate: 采样率
            language: 语言

        Returns:
            识别结果
        """
        url = f"{self.endpoint_url}/api/v2/asr"

        # 读取音频文件
        if Path(audio_file).exists():
            with open(audio_file, 'rb') as f:
                audio_data = f.read()
        else:
            # 如果是URL，下载音频
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_file)
                audio_data = response.content

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.api_key
            },
            "audio": {
                "format": format,
                "sample_rate": sample_rate,
                "language": language
            }
        }

        # 使用multipart上传
        files = {
            "file": ("audio.wav", audio_data, f"audio/{format}")
        }

        data = {
            "payload": json.dumps(payload)
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"文件ASR错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"文件ASR失败: {e.response.text}")

    # ========== 3. 语音合成（TTS） ==========

    async def text_to_speech(self, text: str, voice_type: str = "zh_female_shuangkuaisisi_moon_bigtts",
                             speed: float = 1.0, pitch: float = 1.0, volume: float = 1.0,
                             format: str = "mp3", sample_rate: int = 24000) -> bytes:
        """
        文字转语音

        Args:
            text: 要合成的文本
            voice_type: 音色（默认为双快思思）
            speed: 语速（0.2-3.0，默认1.0）
            pitch: 音调（-12到12，默认1.0）
            volume: 音量（0.1-10.0，默认1.0）
            format: 音频格式（mp3/wav/opus等）
            sample_rate: 采样率（24000）

        Returns:
            音频数据（bytes）
        """
        url = f"{self.endpoint_url}/api/v2/tts"

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.api_key
            },
            "user": {
                "uid": "user_001"
            },
            "audio": {
                "voice_type": voice_type,
                "encoding": format,
                "speed": speed,
                "volume": volume,
                "pitch": pitch,
                "sample_rate": sample_rate
            },
            "request": {
                "reqid": f"tts_{asyncio.get_event_loop().time()}",
                "text": text,
                "text_type": "plain",
                "operation": "query"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()

                # 返回音频数据
                if response.headers.get("content-type", "").startswith("audio"):
                    return response.content
                else:
                    # 如果返回JSON，可能是错误
                    result = response.json()
                    if result.get("error_code"):
                        raise Exception(f"TTS错误: {result.get('message')}")
                    return result

        except httpx.HTTPStatusError as e:
            logger.error(f"TTS错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"TTS失败: {e.response.text}")

    # ========== 4. 声音复刻 ==========

    async def clone_voice(self, reference_audio: str, voice_name: str,
                          description: str = "") -> Dict:
        """
        声音复刻

        Args:
            reference_audio: 参考音频文件路径
            voice_name: 音色名称
            description: 音色描述

        Returns:
            复刻结果，包含voice_id
        """
        url = f"{self.endpoint_url}/api/v2/voice/clone"

        # 读取参考音频
        if Path(reference_audio).exists():
            with open(reference_audio, 'rb') as f:
                audio_data = f.read()
        else:
            raise FileNotFoundError(f"参考音频不存在: {reference_audio}")

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.api_key
            },
            "user": {
                "uid": "user_001"
            },
            "audio": {
                "voice_name": voice_name,
                "sample_rate": 24000,
                "encoding": "mp3"
            },
            "request": {
                "reqid": f"clone_{asyncio.get_event_loop().time()}",
                "operation": "submit"
            }
        }

        files = {
            "file": ("reference.mp3", audio_data, "audio/mpeg")
        }

        data = {
            "payload": json.dumps(payload)
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                result = response.json()

                if result.get("error_code"):
                    raise Exception(f"声音复刻错误: {result.get('message')}")

                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"声音复刻错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"声音复刻失败: {e.response.text}")

    async def check_clone_status(self, clone_id: str) -> Dict:
        """
        查询声音复刻状态

        Args:
            clone_id: 复刻任务ID

        Returns:
            复刻状态
        """
        url = f"{self.endpoint_url}/api/v2/voice/clone"

        payload = {
            "app": {
                "appid": self.app_id,
                "token": self.api_key
            },
            "request": {
                "operation": "query",
                "reqid": clone_id
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"查询复刻状态失败: {str(e)}")
            raise

    # ========== 5. 同声传译 ==========

    async def streaming_translation(self, audio_data: bytes,
                                    source_language: str = "zh",
                                    target_language: str = "en",
                                    format: str = "wav",
                                    sample_rate: int = 16000) -> AsyncIterator[Dict]:
        """
        同声传译（流式）- 使用豆包AST 2.0 API

        Args:
            audio_data: 音频数据
            source_language: 源语言 (zh/en)
            target_language: 目标语言 (zh/en)
            format: 音频格式 (wav)
            sample_rate: 采样率 (16000)

        Yields:
            翻译结果字典，包含：
            - event: 事件类型
            - text: 文本（原文或译文）
            - data: 音频数据（TTS时）
            - start_time: 开始时间
            - end_time: 结束时间
        """
        import sys
        import os
        from pathlib import Path
        import io
        import wave
        import struct

        # ===== 音频格式验证 =====
        logger.info(f"[AST] 接收到音频数据: {len(audio_data)} bytes")

        try:
            # 验证音频数据长度
            if len(audio_data) < 8000:  # 至少0.25秒 @ 16kHz
                error_msg = f"音频太短: {len(audio_data)} bytes (< 8000)，建议至少1秒(32000 bytes)"
                logger.error(f"[AST] {error_msg}")
                yield {
                    "event": "error",
                    "error": error_msg,
                    "type": "AudioTooShortError"
                }
                return

            # 检查是否是纯PCM数据（无WAV头）还是完整WAV文件
            # 纯PCM数据不会以"RIFF"开头
            has_wav_header = len(audio_data) >= 4 and audio_data[:4] == b'RIFF'

            if has_wav_header:
                # 完整WAV文件，需要验证格式
                logger.info(f"[AST] 检测到WAV文件头，进行格式验证")
                audio_file = io.BytesIO(audio_data)
                try:
                    with wave.open(audio_file, 'rb') as wav:
                        nchannels = wav.getnchannels()
                        sampwidth = wav.getsampwidth()
                        framerate = wav.getframerate()

                        logger.info(f"[AST] 音频格式: {nchannels}ch, {sampwidth*8}bit, {framerate}Hz")

                        if nchannels != 1:
                            error_msg = f"音频通道数错误: 应为单声道(1)，当前为{nchannels}"
                            logger.error(f"[AST] {error_msg}")
                            yield {
                                "event": "error",
                                "error": error_msg,
                                "type": "InvalidAudioFormatError",
                                "details": {
                                    "expected": "1 (mono)",
                                    "actual": str(nchannels)
                                }
                            }
                            return

                        if framerate != 16000:
                            error_msg = f"音频采样率错误: 应为16000Hz，当前为{framerate}Hz"
                            logger.error(f"[AST] {error_msg}")
                            yield {
                                "event": "error",
                                "error": error_msg,
                                "type": "InvalidAudioFormatError",
                                "details": {
                                    "expected": "16000",
                                    "actual": str(framerate)
                                }
                            }
                            return

                        if sampwidth != 2:
                            error_msg = f"音频采样宽度错误: 应为2(16bit)，当前为{sampwidth}"
                            logger.error(f"[AST] {error_msg}")
                            yield {
                                "event": "error",
                                "error": error_msg,
                                "type": "InvalidAudioFormatError",
                                "details": {
                                    "expected": "2 (16bit)",
                                    "actual": str(sampwidth)
                                }
                            }
                            return

                        # 提取PCM数据
                        wav.setpos(0)
                        audio_data = wav.readframes(wav.getnframes())
                        logger.info(f"[AST] 从WAV文件提取PCM数据: {len(audio_data)} bytes")

                        # 检查音频内容
                        nframes = wav.getnframes()
                        duration = nframes / framerate
                        logger.info(f"[AST] 音频时长: {duration:.2f}秒")

                        if duration < 0.5:
                            logger.warning(f"[AST] 音频较短: {duration:.2f}秒，可能影响识别效果")

                except wave.Error as e:
                    error_msg = f"音频格式验证失败: {str(e)}"
                    logger.error(f"[AST] {error_msg}")
                    yield {
                        "event": "error",
                        "error": error_msg,
                        "type": "InvalidAudioFormatError"
                    }
                    return
            else:
                # 纯PCM数据（无WAV头），API端点已经验证过格式
                # logger.info(f"[AST] 检测到纯PCM数据（已由API端点验证）")
                # logger.info(f"[AST] 假设格式: 16kHz, 单声道, 16bit")
                # 计算时长
                duration = len(audio_data) / 2 / 16000  # bytes / 2bytes_per_sample / sample_rate
                logger.info(f"[AST] 音频时长: {duration:.2f}秒")

                if duration < 0.5:
                    logger.warning(f"[AST] 音频较短: {duration:.2f}秒，可能影响识别效果")

        except Exception as e:
            logger.error(f"[AST] 音频验证失败: {e}")
            yield {
                "event": "error",
                "error": str(e),
                "type": "AudioValidationError"
            }
            return

        # 添加protobuf模块路径
        protobuf_path = Path(__file__).parent / "protobuf"
        sys.path.insert(0, str(protobuf_path))

        try:
            from base.plugins.llm.services.protobuf import doubao_ast_pb2
        except ImportError as e:
            logger.error(f"无法导入protobuf模块: {e}")
            logger.error(f"protobuf_path: {protobuf_path}")
            logger.error(f"sys.path: {sys.path}")
            raise Exception("Protobuf模块未正确编译，请运行: cd base/plugins/llm/services/protobuf && python -m grpc_tools.protoc --proto_path=. --python_out=. doubao_ast.proto")

        # 导入protobuf模块
        from base.plugins.llm.services.protobuf import doubao_ast_pb2

        # 正确的API端点
        ws_url = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"

        # 生成唯一的session_id
        import uuid
        session_id = str(uuid.uuid4())

        # 使用保存的认证信息
        # 对于AST 2.0服务，优先使用api_id和access_token
        app_id = self.api_id or ""
        app_key = self.access_token or self.api_key or ""

        # 如果api_key包含冒号，可能是 app_id:secret 格式
        if self.api_key and ':' in self.api_key and not app_id:
            parts = self.api_key.split(':', 1)
            if len(parts) == 2:
                app_id = parts[0]
                app_key = parts[1]

        # 构建认证Header
        if not app_id or not app_key:
            error_msg = f"AST认证信息缺失: api_id={'已设置' if app_id else '未设置'}, access_token={'已设置' if app_key else '未设置'}。请在API Key配置中添加 api_id 和 access_token 字段。"
            logger.error(f"[AST] {error_msg}")
            logger.error(f"[AST] 请访问数据库表 llm_api_key，为豆包服务(model_service_type='voice')配置正确的 api_id 和 access_token")
            yield {
                "event": "error",
                "error": error_msg,
                "type": "MissingCredentialsError"
            }
            return

        # 生成唯一的连接ID（官方demo包含此字段）
        import uuid
        conn_id = str(uuid.uuid4())

        headers = {
            "X-Api-App-Key": app_id,
            "X-Api-Access-Key": app_key,
            "X-Api-Resource-Id": "volc.service_type.10053",
            "X-Api-Connect-Id": conn_id  # 官方demo的关键字段
        }

        logger.info(f"[AST] 开始同声传译会话: {session_id}")
        logger.info(f"[AST] 源语言: {source_language}, 目标语言: {target_language}")
        logger.info(f"[AST] 认证信息: app_id={app_id[:8] + '...' if app_id else 'None'}, app_key={app_key[:8] + '...' if app_key else 'None'}")
        logger.info(f"[AST] 使用官方demo配置: 分块=3200 bytes, 延迟=100ms, ping_interval=None")
        logger.info(f"[AST] 请求头: X-Api-App-Key={app_id}, X-Api-Connect-Id={conn_id[:8]}...")

        try:
            # 使用官方demo的WebSocket配置
            async with websockets.connect(
                ws_url,
                additional_headers=headers,
                max_size=1000000000,    # 官方demo: 1GB
                ping_interval=None      # 官方demo: 禁用ping
            ) as ws:
                logger.info(f"[AST] WebSocket连接已建立")

                # ========== 步骤1: 发送StartSession (event=100) ==========
                start_session = doubao_ast_pb2.StartSessionRequest()
                start_session.request_meta.session_id = session_id
                start_session.event = 100  # StartSession

                # 用户信息
                start_session.user.uid = "user_001"
                start_session.user.did = "device_001"
                start_session.user.platform = "Linux"
                start_session.user.sdk_version = "1.0.0"

                # 请求配置
                start_session.request.mode = "s2s"  # Speech-to-Speech
                start_session.request.source_language = source_language
                start_session.request.target_language = target_language
                start_session.request.service_name = "translate"  # 服务名称（必需）

                # 源音频配置
                start_session.source_audio.format = "wav"
                start_session.source_audio.codec = "raw"
                start_session.source_audio.rate = 16000
                start_session.source_audio.bits = 16
                start_session.source_audio.channel = 1

                # 目标音频配置（使用官方demo的格式）
                start_session.target_audio.format = "ogg_opus"  # 官方demo: ogg_opus
                start_session.target_audio.rate = 24000

                # 序列化并发送
                start_data = start_session.SerializeToString()
                await ws.send(start_data)
                logger.info(f"[AST] 发送StartSession ({len(start_data)} bytes)")

                # ========== 步骤2: 等待SessionStarted (event=150) ==========
                response_data = await ws.recv()
                logger.info(f"[AST] 收到响应 ({len(response_data)} bytes)")

                # 解析响应
                response = doubao_ast_pb2.SessionStartedResponse()
                response.ParseFromString(response_data)

                if response.response_meta.status_code != 20000000:
                    error_msg = response.response_meta.message or "未知错误"
                    raise Exception(f"建联失败: {error_msg} (status_code: {response.response_meta.status_code})")

                logger.info(f"[AST] 会话已建立 (session_id: {response.response_meta.session_id})")

                # ========== 步骤3: 发送音频数据 TaskRequest (event=200) ==========
                # 使用官方demo的分块大小：3200 bytes (100ms)
                chunk_size = 3200  # 官方demo: 100ms chunks
                total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

                logger.info(f"[AST] 发送音频数据: {len(audio_data)} bytes, 分为 {total_chunks} 块")

                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i + chunk_size]

                    task_request = doubao_ast_pb2.TaskRequest()
                    task_request.event = 200  # TaskRequest
                    task_request.source_audio.data = chunk

                    task_data = task_request.SerializeToString()
                    await ws.send(task_data)

                    if (i // chunk_size + 1) % 10 == 0:  # 每10块打印一次
                        logger.info(f"[AST] 已发送 {i // chunk_size + 1}/{total_chunks} 块")

                    # 关键修复：使用官方demo的延迟 (100ms)
                    await asyncio.sleep(0.1)

                # ========== 步骤4: 发送FinishSession (event=102) ==========
                finish_session = doubao_ast_pb2.FinishSessionRequest()
                finish_session.event = 102  # FinishSession

                finish_data = finish_session.SerializeToString()
                await ws.send(finish_data)
                logger.info(f"[AST] 发送FinishSession")

                # ========== 步骤5: 接收翻译结果 ==========
                logger.info(f"[AST] 开始接收翻译结果...")

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

                async for response_data in ws:
                    # 尝试解析不同类型的响应
                    event = None

                    # 从响应中提取event字段
                    # Protobuf消息的第一个字段通常是event或response_meta
                    try:
                        # 尝试解析为各种响应类型
                        # 首先读取event字段（如果存在）
                        if len(response_data) > 0:
                            # 简单的event检测：event通常是varint编码
                            # 我们需要尝试不同的消息类型

                            # 方法1：尝试解析所有可能的响应类型
                            response_types = [
                                doubao_ast_pb2.SourceSubtitleStart,
                                doubao_ast_pb2.SourceSubtitleResponse,
                                doubao_ast_pb2.SourceSubtitleEnd,
                                doubao_ast_pb2.TranslationSubtitleStart,
                                doubao_ast_pb2.TranslationSubtitleResponse,
                                doubao_ast_pb2.TranslationSubtitleEnd,
                                doubao_ast_pb2.TTSSentenceStart,
                                doubao_ast_pb2.TTSResponse,
                                doubao_ast_pb2.TTSSentenceEnd,
                                doubao_ast_pb2.UsageResponse,
                                doubao_ast_pb2.SessionFinishedResponse,
                                doubao_ast_pb2.SessionFailedResponse,
                                doubao_ast_pb2.AudioMuted
                            ]

                            parsed = False
                            for resp_type in response_types:
                                try:
                                    response = resp_type()
                                    response.ParseFromString(response_data)

                                    # 根据不同的响应类型处理
                                    if hasattr(response, 'event'):
                                        event = response.event
                                        parsed = True

                                        # 处理原文响应
                                        if event == 651:  # SourceSubtitleResponse
                                            text = response.text if hasattr(response, 'text') else ""
                                            logger.info(f"[AST] 原文: {text}")
                                            final_result["source_segments"].append(text)
                                            yield {
                                                "event": "source_subtitle",
                                                "text": text
                                            }

                                        # 处理译文响应
                                        elif event == 654:  # TranslationSubtitleResponse
                                            text = response.text if hasattr(response, 'text') else ""
                                            logger.info(f"[AST] 译文: {text}")
                                            final_result["translation_segments"].append(text)
                                            yield {
                                                "event": "translation_subtitle",
                                                "text": text
                                            }

                                        # 处理TTS音频
                                        elif event == 352:  # TTSResponse
                                            data = response.data if hasattr(response, 'data') else b""
                                            logger.info(f"[AST] TTS音频: {len(data)} bytes")
                                            final_result["audio_data"] += data
                                            yield {
                                                "event": "tts_audio",
                                                "data": data
                                            }

                                        # 处理计量计费
                                        elif event == 154:  # UsageResponse
                                            if hasattr(response, 'response_meta') and hasattr(response.response_meta, 'billing'):
                                                billing = response.response_meta.billing
                                                final_result["duration_ms"] = billing.duration_msec if hasattr(billing, 'duration_msec') else 0

                                                for item in billing.items:
                                                    unit = item.unit if hasattr(item, 'unit') else ""
                                                    quantity = item.quantity if hasattr(item, 'quantity') else 0
                                                    final_result["tokens"][unit] = quantity
                                                    logger.info(f"[AST] Token使用: {unit} = {quantity}")

                                        # 会话结束
                                        elif event == 152:  # SessionFinished
                                            logger.info(f"[AST] 会话正常结束")
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
                                            
                                            final_result["source_text"] = smart_join(final_result["source_segments"])
                                            final_result["translation_text"] = smart_join(final_result["translation_segments"])
                                            yield {
                                                "event": "session_finished",
                                                "result": final_result
                                            }
                                            break

                                        # 会话失败
                                        elif event == 153:  # SessionFailed
                                            error_msg = "未知错误"
                                            error_code = "UNKNOWN"
                                            if hasattr(response, 'response_meta'):
                                                error_msg = response.response_meta.message or error_msg
                                                error_code = str(response.response_meta.status_code) if hasattr(response.response_meta, 'status_code') else "UNKNOWN"
                                            logger.error(f"[AST] 会话失败: [{error_code}] {error_msg}")

                                            # 发送错误事件
                                            yield {
                                                "event": "error",
                                                "error": error_msg,
                                                "error_code": error_code,
                                                "type": "SessionFailedError"
                                            }
                                            break  # 退出循环

                                    break
                                except Exception as e:
                                    # 解析失败，尝试下一个类型
                                    continue

                            if not parsed:
                                # 如果无法解析，记录日志并继续
                                logger.warning(f"[AST] 无法解析响应 ({len(response_data)} bytes): {response_data[:100].hex()}")

                                # 如果收到多个连续无法解析的消息，可能是会话已结束
                                # 添加一个计数器或标志来检测这种情况
                                # 这里暂时跳过，继续等待下一个响应
                                pass

                    except Exception as e:
                        logger.warning(f"[AST] 解析响应时出错: {e}")

                logger.info(f"[AST] 同声传译完成")
                logger.info(f"[AST] 原文: {final_result['source_text']}")
                logger.info(f"[AST] 译文: {final_result['translation_text']}")
                logger.info(f"[AST] 音频时长: {final_result['duration_ms']}ms")
                logger.info(f"[AST] Token使用: {final_result['tokens']}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"[AST] WebSocket连接关闭: {e}")
            raise Exception(f"WebSocket连接异常关闭: {e}")
        except Exception as e:
            logger.error(f"[AST] 同声传译失败: {str(e)}", exc_info=True)
            raise

    # ========== 辅助方法 ==========

    @staticmethod
    async def save_audio_file(audio_data: bytes, directory: str = "uploads/voice") -> str:
        """
        保存音频文件

        Args:
            audio_data: 音频数据
            directory: 保存目录

        Returns:
            文件路径
        """
        import os
        import uuid

        # 确保目录存在
        os.makedirs(directory, exist_ok=True)

        # 生成唯一文件名
        filename = f"{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(directory, filename)

        # 保存文件
        with open(filepath, 'wb') as f:
            f.write(audio_data)

        return filepath

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算token数量"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)
