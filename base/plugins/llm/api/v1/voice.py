"""
语音API接口 - 支持语音专用API Key
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, FileResponse
from typing import Optional
import logging
import json

from base.common.response import SuccessResponse
from base.common.security import get_current_user_id
# 从统一的使用记录表导入
from base.plugins.llm.models.usage import LLMUsageRecord
from base.plugins.llm.services.voice_helper import VoiceServiceHelper

logger = logging.getLogger(__name__)

voice_router = APIRouter(
    prefix="/voice",
    tags=["语音服务"],
    dependencies=[Depends(get_current_user_id)]
)

# 测试endpoint：验证新代码是否加载
@voice_router.get("/test/new_code", summary="测试新代码是否加载")
async def test_new_code():
    """测试新的audio_format_utils是否可用"""
    try:
        from base.plugins.llm.services.audio_format_utils import detect_audio_format
        return {
            "status": "success",
            "message": "新代码已加载",
            "module": "audio_format_utils",
            "available_functions": ["detect_audio_format", "convert_float32_to_int16_pcm", "convert_audio_to_wav"]
        }
    except ImportError as e:
        return {
            "status": "error",
            "message": "新代码未加载",
            "error": str(e)
        }


# ========== 1. 流式语音识别 ==========

@voice_router.post("/asr/streaming", summary="流式语音识别")
async def streaming_asr(
    audio_file: UploadFile,
    provider_id: int = Form(..., description="厂商ID"),
    format: str = Form("wav"),
    sample_rate: int = Form(16000),
    language: str = Form("zh"),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    流式语音识别（实时）

    上传音频文件进行实时语音识别
    """
    try:
        # 获取语音服务（自动使用语音专用API Key）
        service = await VoiceServiceHelper.get_voice_service(provider_id)

        # 读取音频数据（支持流式传输）
        audio_data = b''
        chunk_size = 8192
        while True:
            chunk = await audio_file.read(chunk_size)
            if not chunk:
                break
            audio_data += chunk
        logger.info(f"[streaming_asr] 读取音频数据: {len(audio_data)} bytes")

        # 创建记录（使用UUID避免重复）
        import uuid
        from datetime import datetime
        import pytz
        record = await LLMUsageRecord.create(
            record_id=f"asr_{uuid.uuid4().hex[:16]}",
            customer_id=current_user_id,
            model_id=provider_id,
            record_type="voice",
            audio_file=audio_file.filename,
            audio_format=format,
            status="processing",
            start_time=datetime.now(pytz.UTC)
        )

        # 调用服务
        results = []
        async for result in service.streaming_asr(audio_data, format, sample_rate, language):
            results.append(result)

        # 更新记录
        if results:
            final_result = results[-1]
            end_time = datetime.now(pytz.UTC)
            duration_seconds = 0
            if record.start_time:
                duration_seconds = int((end_time - record.start_time).total_seconds())
            
            await LLMUsageRecord.filter(id=record.id).update(
                input_text=final_result.get("text", ""),
                audio_duration=duration_seconds,
                status="completed",
                end_time=end_time
            )

        # 更新使用量
        await VoiceServiceHelper.update_voice_usage(service, tokens=100)

        return SuccessResponse(data={
            "record_id": record.record_id,
            "results": results
        })

    except Exception as e:
        logger.error(f"流式ASR失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"流式ASR失败: {str(e)}")


# ========== 2. 录音文件识别 ==========

@voice_router.post("/asr/file", summary="录音文件识别")
async def file_asr(
    audio_file: UploadFile,
    provider_id: int = Form(..., description="厂商ID"),
    format: str = Form("wav"),
    sample_rate: int = Form(16000),
    language: str = Form("zh"),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    上传音频文件进行语音识别
    """
    try:
        # 获取语音服务
        service = await VoiceServiceHelper.get_voice_service(provider_id)

        # 保存音频文件（支持流式传输）
        audio_data = b''
        chunk_size = 8192
        while True:
            chunk = await audio_file.read(chunk_size)
            if not chunk:
                break
            audio_data += chunk

        from base.plugins.llm.services.doubao_voice_service import DoubaoVoiceService
        audio_path = await DoubaoVoiceService.save_audio_file(audio_data)

        # 创建记录（使用UUID避免重复）
        import uuid
        from datetime import datetime
        import pytz
        record = await LLMUsageRecord.create(
            record_id=f"file_asr_{uuid.uuid4().hex[:16]}",
            customer_id=current_user_id,
            model_id=provider_id,
            record_type="voice",
            audio_file=audio_path,
            audio_format=format,
            status="processing",
            start_time=datetime.now(pytz.UTC)
        )

        # 调用服务
        result = await service.file_asr(audio_path, format, sample_rate, language)

        # 更新记录
        if result.get("result") == "success":
            end_time = datetime.now(pytz.UTC)
            duration_seconds = 0
            if record.start_time:
                duration_seconds = int((end_time - record.start_time).total_seconds())
            
            await LLMUsageRecord.filter(id=record.id).update(
                input_text=result.get("text", ""),
                audio_duration=duration_seconds,
                status="completed",
                end_time=end_time
            )

        # 更新使用量
        await VoiceServiceHelper.update_voice_usage(service, tokens=100)

        return SuccessResponse(data={
            "record_id": record.record_id,
            "result": result
        })

    except Exception as e:
        logger.error(f"文件ASR失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件ASR失败: {str(e)}")


# ========== 3. 语音合成 ==========

@voice_router.post("/tts", summary="文字转语音")
async def text_to_speech(
    text: str = Form(..., min_length=1),
    provider_id: int = Form(..., description="厂商ID"),
    voice_type: str = Form("zh_female_shuangkuaisisi_moon_bigtts"),
    speed: float = Form(1.0),
    pitch: float = Form(1.0),
    volume: float = Form(1.0),
    format: str = Form("mp3"),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    文字转语音

    返回音频文件供下载
    """
    try:
        # 获取语音服务（自动使用语音专用API Key）
        service = await VoiceServiceHelper.get_voice_service(provider_id)

        # 创建记录（使用UUID避免重复）
        import uuid
        from datetime import datetime
        import pytz
        record = await LLMUsageRecord.create(
            record_id=f"tts_{uuid.uuid4().hex[:16]}",
            customer_id=current_user_id,
            model_id=provider_id,
            record_type="tts",
            input_text=text,
            voice_type=voice_type,
            speed=speed,
            pitch=pitch,
            volume=volume,
            audio_format=format,
            status="processing",
            start_time=datetime.now(pytz.UTC)
        )

        # 调用服务
        audio_data = await service.text_to_speech(
            text, voice_type, speed, pitch, volume, format
        )

        # 保存音频文件
        from base.plugins.llm.services.doubao_voice_service import DoubaoVoiceService
        audio_path = await DoubaoVoiceService.save_audio_file(audio_data)

        # 更新记录
        from pathlib import Path
        from datetime import datetime
        import pytz
        audio_size = len(audio_data)
        end_time = datetime.now(pytz.UTC)
        duration_seconds = 0
        if record.start_time:
            duration_seconds = int((end_time - record.start_time).total_seconds())
        
        await LLMUsageRecord.filter(id=record.id).update(
            audio_file=audio_path,
            audio_duration=duration_seconds,
            tokens=DoubaoVoiceService.estimate_tokens(text),
            status="completed",
            end_time=end_time
        )

        # 更新使用量
        await VoiceServiceHelper.update_voice_usage(
            service,
            tokens=DoubaoVoiceService.estimate_tokens(text)
        )

        # 返回音频文件
        return FileResponse(
            path=audio_path,
            media_type=f"audio/{format}",
            filename=f"{record.record_id}.{format}"
        )

    except Exception as e:
        logger.error(f"TTS失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS失败: {str(e)}")


# ========== 4. 声音复刻 ==========

@voice_router.post("/clone/submit", summary="提交声音复刻任务")
async def submit_clone(
    reference_audio: UploadFile,
    provider_id: int = Form(..., description="厂商ID"),
    voice_name: str = Form(...),
    description: str = Form(""),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    提交声音复刻任务

    上传参考音频，创建自定义音色
    """
    try:
        # 获取语音服务
        service = await VoiceServiceHelper.get_voice_service(provider_id)

        # 保存参考音频（支持流式传输）
        audio_data = b''
        chunk_size = 8192
        while True:
            chunk = await reference_audio.read(chunk_size)
            if not chunk:
                break
            audio_data += chunk

        from base.plugins.llm.services.doubao_voice_service import DoubaoVoiceService
        audio_path = await DoubaoVoiceService.save_audio_file(audio_data)

        # 创建记录
        from datetime import datetime
        import pytz
        import uuid
        clone = await LLMUsageRecord.create(
            record_id=f"clone_{uuid.uuid4().hex[:16]}",
            clone_id=f"clone_{hash(audio_path)}",
            customer_id=current_user_id,
            model_id=provider_id,
            record_type="voice_clone",
            reference_audio=audio_path,
            voice_name=voice_name,
            voice_description=description,
            status="processing",
            start_time=datetime.now(pytz.UTC)
        )

        # 调用服务
        result = await service.clone_voice(audio_path, voice_name, description)

        # 更新记录
        if result.get("voice_id"):
            from datetime import datetime
            import pytz
            end_time = datetime.now(pytz.UTC)
            duration_seconds = 0
            if clone.start_time:
                duration_seconds = int((end_time - clone.start_time).total_seconds())
            
            await LLMUsageRecord.filter(id=clone.id).update(
                voice_id=result.get("voice_id"),
                audio_duration=duration_seconds,
                status="completed",
                end_time=end_time
            )

        # 更新使用量
        await VoiceServiceHelper.update_voice_usage(service, tokens=100)

        return SuccessResponse(data={
            "clone_id": clone.clone_id,
            "voice_id": result.get("voice_id"),
            "status": "submitted"
        })

    except Exception as e:
        logger.error(f"声音复刻失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"声音复刻失败: {str(e)}")


@voice_router.get("/clone/{clone_id}", summary="查询声音复刻状态")
async def check_clone_status(
    clone_id: str,
    provider_id: int = Query(..., description="厂商ID"),
    current_user_id: int = Depends(get_current_user_id)
):
    """查询声音复刻任务状态"""
    try:
        service = await VoiceServiceHelper.get_voice_service(provider_id)
        result = await service.check_clone_status(clone_id)

        return SuccessResponse(data=result)

    except Exception as e:
        logger.error(f"查询复刻状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


# ========== 5. 同声传译 ==========

@voice_router.post("/translation/streaming", summary="同声传译")
async def streaming_translation(
    audio_file: UploadFile,
    provider_id: int = Form(..., description="厂商ID"),
    source_language: str = Form("zh"),
    target_language: str = Form("en"),
    format: str = Form("wav"),
    sample_rate: int = Form(16000),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    同声传译（流式）

    上传音频文件进行实时翻译
    """
    logger.info(f"[DEBUG] streaming_translation 函数开始执行")
    try:
        # 获取语音服务
        service = await VoiceServiceHelper.get_voice_service(provider_id)

        # 读取音频数据（支持流式传输，持续读取所有数据）
        raw_audio_data = b''
        chunk_size = 8192
        while True:
            chunk = await audio_file.read(chunk_size)
            if not chunk:
                break
            raw_audio_data += chunk
            logger.info(f"[DEBUG] 读取音频块: {len(chunk)} bytes, 总计: {len(raw_audio_data)} bytes")

        logger.info(f"[DEBUG] 原始音频数据读取完成: {len(raw_audio_data)} bytes")

        # 关键修复：提取纯PCM数据（不包含WAV头）
        # 豆包AST需要纯PCM数据，不是完整的WAV文件
        # logger.info(f"[DEBUG] 提取纯PCM数据...")

        import wave
        import io

        try:
            # 使用wave库读取WAV文件并提取纯PCM数据
            audio_file_obj = io.BytesIO(raw_audio_data)
            with wave.open(audio_file_obj, 'rb') as wf:
                # 验证音频格式
                if wf.getnchannels() != 1:
                    raise ValueError(f"音频必须是单声道，当前为{wf.getnchannels()}声道")
                if wf.getframerate() != 16000:
                    raise ValueError(f"音频采样率必须是16000Hz，当前为{wf.getframerate()}Hz")
                if wf.getsampwidth() != 2:
                    raise ValueError(f"音频位深度必须是16bit，当前为{wf.getsampwidth()*8}bit")

                # 读取纯PCM数据（不包含WAV头）
                audio_data = wf.readframes(wf.getnframes())

            logger.info(f"[DEBUG] PCM数据提取成功: {len(audio_data)} bytes")
            logger.info(f"[DEBUG] 原始WAV大小: {len(raw_audio_data)} bytes")
            logger.info(f"[DEBUG] PCM数据大小: {len(audio_data)} bytes")
            logger.info(f"[DEBUG] WAV头大小: {len(raw_audio_data) - len(audio_data)} bytes")

            # 保存调试音频文件（分步骤保存，便于对比）
            import time
            from pathlib import Path
            debug_dir = Path("debug_audio")
            debug_dir.mkdir(exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")

            # 步骤1: 保存原始上传文件
            raw_filename = debug_dir / f"1_raw_upload_{timestamp}.wav"
            with open(str(raw_filename), 'wb') as f:
                f.write(raw_audio_data)
            logger.info(f"[音频调试-步骤1] 原始上传文件: {raw_filename.name} ({len(raw_audio_data)} bytes)")

            # 步骤2: 保存提取的PCM数据
            pcm_filename = debug_dir / f"2_extracted_pcm_{timestamp}.pcm"
            with open(str(pcm_filename), 'wb') as f:
                f.write(audio_data)
            logger.info(f"[音频调试-步骤2] 提取的PCM数据: {pcm_filename.name} ({len(audio_data)} bytes)")

            # 步骤3: 重建WAV文件（用于验证提取是否正确）
            import wave as wave_module
            reconstructed_filename = debug_dir / f"3_reconstructed_wav_{timestamp}.wav"
            with wave_module.open(str(reconstructed_filename), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_data)
            logger.info(f"[音频调试-步骤3] 重建的WAV文件: {reconstructed_filename.name}")

            # 验证重建的文件
            with wave_module.open(str(reconstructed_filename), 'rb') as vf:
                reconstructed_pcm = vf.readframes(vf.getnframes())
            logger.info(f"[音频调试-步骤4] 验证重建文件: PCM大小={len(reconstructed_pcm)} bytes, 一致性={len(reconstructed_pcm) == len(audio_data)}")

            # 步骤5: 保存发送给豆包的数据
            doubao_filename = debug_dir / f"4_for_doubao_{timestamp}.pcm"
            with open(str(doubao_filename), 'wb') as f:
                f.write(audio_data)
            logger.info(f"[音频调试-步骤5] 发送给豆包的数据: {doubao_filename.name} ({len(audio_data)} bytes)")
            logger.info(f"[音频调试] 总计保存了5个文件用于对比分析")

        except wave.Error as e:
            # 如果不是WAV格式，尝试其他方式
            logger.warning(f"[DEBUG] 无法用wave库读取: {e}")
            logger.info(f"[DEBUG] 尝试使用audio_format_utils...")

            from base.plugins.llm.services.audio_format_utils import convert_audio_to_wav
            converted_data, audio_info = convert_audio_to_wav(
                raw_audio_data,
                filename=audio_file.filename,
                sample_rate=sample_rate,
                channels=1,
                bits=16
            )

            # 转换后的数据仍然是WAV格式，需要再次提取PCM
            if audio_info['final_format'] == 'wav':
                audio_file_obj = io.BytesIO(converted_data)
                with wave.open(audio_file_obj, 'rb') as wf:
                    audio_data = wf.readframes(wf.getnframes())
                logger.info(f"[DEBUG] 转换后PCM数据: {len(audio_data)} bytes")
            else:
                audio_data = converted_data

        # 创建记录（使用UUID避免重复）
        import uuid
        from datetime import datetime
        import pytz
        record = await LLMUsageRecord.create(
            record_id=f"trans_{uuid.uuid4().hex[:16]}",
            customer_id=current_user_id,
            model_id=provider_id,
            record_type="voice",
            audio_file=audio_file.filename,
            audio_format=format,
            source_language=source_language,
            target_language=target_language,
            status="processing",
            start_time=datetime.now(pytz.UTC)
        )

        # 调用服务
        results = []
        final_result = None

        async for result in service.streaming_translation(
            audio_data, source_language, target_language, format, sample_rate
        ):
            results.append(result)

            # 最后一个是session_finished事件，包含完整结果
            if result.get("event") == "session_finished":
                final_result = result.get("result", {})

        # 更新记录
        if final_result:
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

            # 更新使用量（如果有token信息）
            tokens = final_result.get("tokens", {})
            total_tokens = sum(tokens.values()) if tokens else 100
            await VoiceServiceHelper.update_voice_usage(service, tokens=int(total_tokens))
        else:
            # 如果没有最终结果，仍然更新使用量
            await VoiceServiceHelper.update_voice_usage(service, tokens=100)

        return SuccessResponse(data={
            "record_id": record.record_id,
            "results": results,
            "final_result": final_result
        })

    except Exception as e:
        logger.error(f"同声传译失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"同声传译失败: {str(e)}")


# ========== 查询接口 ==========

@voice_router.get("/records", summary="获取语音记录列表")
async def get_voice_records(
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    current_user_id: int = Depends(get_current_user_id)
):
    """获取语音相关记录"""
    query = LLMUsageRecord.filter(customer_id=current_user_id, record_type__in=["voice", "tts", "voice_clone"])

    if record_type:
        query = query.filter(record_type=record_type)
    if status:
        query = query.filter(status=status)

    total = await query.count()
    records = await query.offset((page - 1) * page_size).limit(page_size).order_by('-created_at')

    result = []
    for record in records:
        result.append({
            "id": record.id,
            "record_id": record.record_id,
            "record_type": record.record_type,
            "audio_file": record.audio_file,
            "input_text": record.input_text,
            "output_text": record.output_text,
            "voice_type": record.voice_type,
            "source_language": record.source_language,
            "target_language": record.target_language,
            "status": record.status,
            "created_at": record.created_at.isoformat() if record.created_at else None
        })

    return SuccessResponse(data={
        "items": result,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@voice_router.get("/tts/records", summary="获取语音合成记录")
async def get_tts_records(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    current_user_id: int = Depends(get_current_user_id)
):
    """获取语音合成记录"""
    query = LLMUsageRecord.filter(customer_id=current_user_id, record_type="tts")

    if status:
        query = query.filter(status=status)

    total = await query.count()
    records = await query.offset((page - 1) * page_size).limit(page_size).order_by('-created_at')

    result = []
    for record in records:
        result.append({
            "id": record.id,
            "record_id": record.record_id,
            "input_text": record.input_text[:100] + "..." if record.input_text and len(record.input_text) > 100 else record.input_text,
            "voice_type": record.voice_type,
            "audio_file": record.audio_file,
            "status": record.status,
            "created_at": record.created_at.isoformat() if record.created_at else None
        })

    return SuccessResponse(data={
        "items": result,
        "total": total,
        "page": page,
        "page_size": page_size
    })
