"""素材服务：上传存储（本地专用目录）/ 访问 / 素材库 CRUD / 归属隔离。

存储布局（相对 storage/contentops/media/）：
    {owner_type}-{owner_id}/content-{content_id|draft}/{kind}/{uuid}.{ext}
    kind = image / cover / video / adapted
"""
import io
import uuid
from pathlib import Path
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import MediaAsset

# services -> contentops -> plugins -> base -> 项目根
STORAGE_ROOT = Path(__file__).resolve().parents[4] / "storage" / "contentops" / "media"

# 允许类型与扩展名
IMAGE_TYPES = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "image/bmp": ".bmp",
}
VIDEO_TYPES = {
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/x-msvideo": ".avi",
    "video/webm": ".webm", "video/x-matroska": ".mkv",
}
MAX_IMAGE_SIZE = 20 * 1024 * 1024       # 图片 20MB
MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 视频 2GB（本地目录起步）


class MediaService:
    """素材资产服务（归属隔离）。"""

    @staticmethod
    def _dir_for(owner: Optional[OwnerContext], content_id: Optional[int], kind: str) -> Path:
        owner_key = f"{owner.owner_type}-{owner.owner_id}" if owner else "usr-anon"
        content_key = f"content-{content_id}" if content_id else "draft"
        return STORAGE_ROOT / owner_key / content_key / kind

    @staticmethod
    async def upload(
        data: bytes, content_type: str, filename: str, kind: str,
        owner: Optional[OwnerContext], content_id: Optional[int] = None,
        uploader_id: Optional[int] = None, tags: Optional[list] = None,
    ) -> dict:
        """保存文件到磁盘并落 MediaAsset 记录。"""
        is_video = kind == "video"
        allowed = VIDEO_TYPES if is_video else IMAGE_TYPES
        if content_type not in allowed:
            raise ValueError(f"不支持的文件类型: {content_type}（{kind}）")
        max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE
        if len(data) > max_size:
            raise ValueError(f"文件超过大小限制（{max_size // 1024 // 1024}MB）")

        ext = allowed[content_type]
        save_dir = MediaService._dir_for(owner, content_id, kind)
        save_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{uuid.uuid4().hex}{ext}"
        (save_dir / fname).write_bytes(data)
        rel_path = str(save_dir.relative_to(STORAGE_ROOT) / fname)

        # 探测尺寸
        width = height = None
        duration = None
        if not is_video:
            try:
                from PIL import Image
                with Image.open(io.BytesIO(data)) as im:
                    width, height = im.size
            except Exception:
                pass
        else:
            meta = MediaService.probe_video(save_dir / fname)
            width, height, duration = meta["width"], meta["height"], meta["duration"]

        asset = await MediaAsset.create(
            content_id=content_id, kind=kind, filename=fname, rel_path=rel_path,
            url=f"/api/v1/contentops/media/file/{0}",  # 创建后回填真实 id
            content_type=content_type, size_bytes=len(data),
            width=width, height=height, duration_sec=duration,
            tags=tags or [], ocr_status="pending", extra={"original_name": filename},
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
            uploader_id=uploader_id,
        )
        asset.url = f"/api/v1/contentops/media/file/{asset.id}"
        await asset.save(update_fields=["url"])
        return await asset.to_dict()

    @staticmethod
    def probe_video(path: Path) -> dict:
        """用系统 ffmpeg（PATH）探测宽高/时长；无 ffmpeg 时返回空值不抛异常。

        M7：移除 imageio-ffmpeg 本地依赖；探测属元信息增强，缺失不影响上传。
        """
        result = {"width": None, "height": None, "duration": None}
        try:
            import shutil
            exe = shutil.which("ffmpeg")
            if not exe:
                return result
            import subprocess
            import re
            proc = subprocess.run([exe, "-i", str(path)], capture_output=True, text=True, timeout=20)
            info = proc.stderr
            m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", info)
            if m:
                result["width"], result["height"] = int(m.group(1)), int(m.group(2))
            d = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", info)
            if d:
                result["duration"] = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
        except Exception:
            pass
        return result

    @staticmethod
    def file_path(asset: MediaAsset) -> Path:
        """由 rel_path 还原绝对路径，并阻止目录穿越。"""
        target = (STORAGE_ROOT / asset.rel_path).resolve()
        root = STORAGE_ROOT.resolve()
        if root not in target.parents and target != root:
            raise ValueError("非法素材路径")
        return target

    @staticmethod
    async def get_file_asset(asset_id: int, owner: Optional[OwnerContext]) -> MediaAsset:
        return await get_owned_or_404(MediaAsset, asset_id, owner)

    @staticmethod
    async def list_assets(
        owner: Optional[OwnerContext], content_id: Optional[int] = None,
        kind: Optional[str] = None,
    ) -> list:
        qs = owned_queryset(MediaAsset, owner) if owner else MediaAsset.all()
        if content_id:
            qs = qs.filter(content_id=content_id)
        if kind:
            qs = qs.filter(kind=kind)
        return [await a.to_dict() for a in await qs.order_by("-created_at")]

    @staticmethod
    async def bind_to_content(asset_ids: list[int], content_id: int, owner: Optional[OwnerContext]) -> int:
        """把 draft 上传的素材绑定到源内容。仅归属内素材可绑定。"""
        count = 0
        for aid in asset_ids:
            asset = await get_owned_or_404(MediaAsset, aid, owner, for_write=True)
            asset.content_id = content_id
            await asset.save(update_fields=["content_id"])
            count += 1
        return count

    @staticmethod
    async def delete_asset(asset_id: int, owner: Optional[OwnerContext]) -> bool:
        asset = await get_owned_or_404(MediaAsset, asset_id, owner, for_write=True)
        path = MediaService.file_path(asset)
        await asset.delete()
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        return True

    @staticmethod
    async def cleanup_content_files(content_id: int, owner: Optional[OwnerContext]):
        """删除内容时清理其下所有素材文件（由 content_service 调用）。"""
        assets = await MediaService.list_assets(owner, content_id=content_id)
        for a in assets:
            p = STORAGE_ROOT / a["rel_path"]
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
        await MediaAsset.filter(content_id=content_id).delete()

    @staticmethod
    async def update_ocr(asset_id: int, text: str, status: str = "done") -> dict:
        asset = await MediaAsset.get_or_none(id=asset_id)
        if not asset:
            raise ValueError("素材不存在")
        asset.ocr_text = text
        asset.ocr_status = status
        await asset.save(update_fields=["ocr_text", "ocr_status"])
        return await asset.to_dict()
