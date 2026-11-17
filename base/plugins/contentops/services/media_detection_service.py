"""多媒体检测服务：图片/视频文字提取（M7 起全部走线上多模态，无本地模型依赖）。

变更（M7）：删除 rapidocr-onnxruntime / faster-whisper / imageio-ffmpeg 等本地模型依赖，
统一改走 llm 模块的线上视觉模型（VisionAdapter）。设计原则：
- 未配置视觉模型（llm 模块四表空）→ 明确返回 ocr_status='unavailable'，不抛异常、不阻塞上传；
- 配置后 → 图片直接送视觉模型提取文字；视频抽帧后逐帧识别（帧提取用可选 ffmpeg，见下）；
- PII 脱敏在 VisionAdapter 完成，素材检测只消费文本。

视频抽帧说明：不强制 imageio-ffmpeg。若运行环境有系统 ffmpeg（PATH 中）则抽帧识别画面文字；
否则跳过抽帧、仅返回 asr_status='unavailable'（去掉本地 ASR 模型），由文本合规链继续工作。
"""
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from base.plugins.contentops.services.media_service import MediaService
from base.plugins.contentops.models import MediaAsset
from base.plugins.contentops.services.vision_adapter import VisionAdapter

# 视频抽帧最大帧数（防长视频爆炸）
MAX_FRAMES = 30


def _ffmpeg_exe() -> Optional[str]:
    """优先系统 ffmpeg（PATH）。不再依赖 imageio-ffmpeg 包。"""
    return shutil.which("ffmpeg")


async def _recognize(path: Path) -> str:
    """线上视觉模型识别单图文字；未配置/失败抛可读异常由调用方降级。"""
    text, _meta = await VisionAdapter.recognize_image(path)
    return text


class MediaDetectionService:
    """素材文字提取（供合规引擎消费），全部走线上多模态。"""

    @staticmethod
    async def extract_text(asset: MediaAsset) -> dict:
        """按素材类型提取文字。返回 {text, ocr_status, asr_status, frames, mode}。"""
        path = MediaService.file_path(asset)
        if not path.exists():
            raise ValueError(f"素材文件不存在: {asset.id}")

        # 快速探测：未配置线上视觉模型直接降级，不发无效请求
        if not await VisionAdapter.is_configured("vision"):
            return {
                "text": "", "ocr_status": "unavailable", "asr_status": "unavailable",
                "frames": 0, "mode": "online-vision",
                "note": "未配置线上视觉模型（llm 模块 purpose=vision），素材文字提取未启用",
            }

        if asset.kind == "video":
            return await MediaDetectionService._extract_video(path)
        # image / cover / adapted 都按图识别
        try:
            text = await _recognize(path)
            return {"text": text, "ocr_status": "done", "asr_status": "n/a", "frames": 1, "mode": "online-vision"}
        except Exception as e:
            return {
                "text": "", "ocr_status": "failed", "asr_status": "n/a", "frames": 0,
                "mode": "online-vision", "note": f"线上视觉识别失败: {type(e).__name__}: {str(e)[:120]}",
            }

    @staticmethod
    async def _extract_video(path: Path) -> dict:
        """视频：系统 ffmpeg 抽帧 → 逐帧线上识别。无 ffmpeg → 明确降级。"""
        texts: list[str] = []
        asr_status = "unavailable"
        exe = _ffmpeg_exe()
        if not exe:
            return {
                "text": "", "ocr_status": "unavailable", "asr_status": "unavailable", "frames": 0,
                "mode": "online-vision",
                "note": "运行环境无 ffmpeg，视频抽帧未启用；本地 ASR 模型已移除",
            }

        try:
            with tempfile.TemporaryDirectory() as td:
                pattern = str(Path(td) / "frame_%04d.jpg")
                subprocess.run(
                    [exe, "-y", "-i", str(path), "-vf", "fps=0.5", "-frames:v", str(MAX_FRAMES),
                     "-q:v", "5", pattern],
                    capture_output=True, timeout=180,
                )
                frames = sorted(Path(td).glob("frame_*.jpg"))
                for f in frames:
                    try:
                        texts.append(await _recognize(f))
                    except Exception:
                        continue
        except Exception:
            pass

        combined = "\n".join(t for t in texts if t)
        status = "done" if texts else "failed"
        return {
            "text": combined, "ocr_status": status, "asr_status": asr_status,
            "frames": len(texts), "mode": "online-vision",
            "note": "视频语音 ASR 已改为线上（当前未配置语音模型）" if not texts else "",
        }
