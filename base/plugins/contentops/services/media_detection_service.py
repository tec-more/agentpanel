"""多媒体检测服务：图片 OCR / 视频抽帧 OCR / 视频 ASR。

依赖降级策略（不静默跳过）：
- RapidOCR：包内自带模型，缺失/异常 → ocr_status=failed 并抛可读错误
- faster-whisper：首次加载需下载模型（base ≈145MB），懒加载；失败 → ASR 部分跳过并在结果里标注 asr_status=failed，
  抽帧 OCR 仍执行，整体不阻塞上传与合规检测。
"""
import tempfile
from pathlib import Path
from typing import Optional

from base.plugins.contentops.services.media_service import MediaService
from base.plugins.contentops.models import MediaAsset

# 单例惰性加载
_ocr_engine = None
_asr_model = None
_asr_status = "idle"  # idle/ready/failed


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def _get_asr():
    """懒加载 faster-whisper base 模型；失败返回 None 并标记状态。"""
    global _asr_model, _asr_status
    if _asr_model is not None:
        return _asr_model
    if _asr_status == "failed":
        return None
    try:
        import os
        # 境内网络：默认走 hf-mirror 镜像下载模型；已缓存时无需网络。
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from faster_whisper import WhisperModel
        try:
            _asr_model = WhisperModel("base", device="cpu", compute_type="int8")
        except Exception:
            # 缓存损坏时显式快照下载（带镜像），再加载本地快照路径
            from huggingface_hub import snapshot_download
            snapshot = snapshot_download(
                "Systran/faster-whisper-base",
                allow_patterns=["*.bin", "*.json", "*.txt"],
            )
            _asr_model = WhisperModel(snapshot, device="cpu", compute_type="int8")
        _asr_status = "ready"
        return _asr_model
    except Exception as e:
        _asr_status = "failed"
        return None


def ocr_image(path: Path) -> str:
    """单图 OCR，返回拼接文本。失败抛 ValueError。"""
    try:
        result, _ = _get_ocr()(str(path))
    except Exception as e:
        raise ValueError(f"OCR 引擎失败: {type(e).__name__}: {str(e)[:120]}")
    if not result:
        return ""
    # result: [[box, text, score], ...]
    return "\n".join(line[1] for line in result if len(line) >= 2)


class MediaDetectionService:
    """素材文字提取（供合规引擎消费）。"""

    @staticmethod
    async def extract_text(asset: MediaAsset) -> dict:
        """按素材类型提取文字。返回 {text, ocr_status, asr_status, frames}。"""
        path = MediaService.file_path(asset)
        if not path.exists():
            raise ValueError(f"素材文件不存在: {asset.id}")

        if asset.kind == "video":
            return MediaDetectionService._extract_video(path)
        # image / cover / adapted 都按图 OCR
        text = ocr_image(path)
        return {"text": text, "ocr_status": "done", "asr_status": "n/a", "frames": 1}

    @staticmethod
    def _extract_video(path: Path) -> dict:
        """抽帧 OCR + ASR。抽帧失败不掩盖 ASR，反之亦然。"""
        import imageio_ffmpeg
        import subprocess

        texts: list[str] = []
        frame_status = "done"
        asr_status = "n/a"

        # 1) 每 2 秒抽一帧，OCR 提取画面文字（最多 30 帧，防长视频爆炸）
        try:
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            with tempfile.TemporaryDirectory() as td:
                pattern = str(Path(td) / "frame_%04d.jpg")
                subprocess.run(
                    [exe, "-y", "-i", str(path), "-vf", "fps=0.5", "-frames:v", "30",
                     "-q:v", "5", pattern],
                    capture_output=True, timeout=180,
                )
                frames = sorted(Path(td).glob("frame_*.jpg"))
                for f in frames:
                    try:
                        texts.append(ocr_image(f))
                    except Exception:
                        frame_status = "failed"
        except Exception:
            frame_status = "failed"

        # 2) ASR 语音转文字（懒加载，失败降级）
        model = _get_asr()
        if model is not None:
            try:
                segments, _ = model.transcribe(str(path), beam_size=5, language="zh")
                texts.append(" ".join(seg.text for seg in segments))
                asr_status = "done"
            except Exception:
                asr_status = "failed"
        else:
            asr_status = "failed"

        combined = "\n".join(t for t in texts if t)
        overall = "done" if (frame_status == "done" or asr_status == "done") else "failed"
        return {
            "text": combined, "ocr_status": overall,
            "asr_status": asr_status, "frames": len(texts),
        }
