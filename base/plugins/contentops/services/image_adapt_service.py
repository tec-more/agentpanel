"""图片规格自适应（M2）：按比例裁剪/压缩/水印/拼接封面，B站双比例封面。

所有目标规格从 PlatformRuleConfig 读取（禁止硬编码），缺失时用内置默认表兜底。
"""
import io
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from base.common.authz import OwnerContext
from base.plugins.contentops.models import PlatformRuleConfig
from base.plugins.contentops.services.media_service import MediaService
from base.plugins.contentops.models import MediaAsset

# 兜底默认（后台未配置时）；value 结构见 README/PRD
DEFAULT_RATIOS = {
    "wechat": ["2.35:1"], "weibo": ["16:9"], "xiaohongshu": ["3:4"],
    "douyin": ["9:16"], "toutiao": ["16:9"], "bilibili": ["16:9", "4:3"],
}
RATIO_SIZE = {
    "16:9": (1920, 1080), "4:3": (1440, 1080), "2.35:1": (1175, 500),
    "3:4": (1080, 1440), "9:16": (1080, 1920), "1:1": (1080, 1080),
}


def parse_ratio(s: str) -> tuple[int, int]:
    try:
        a, b = s.split(":")
        return int(a), int(b)
    except Exception:
        return 16, 9


def cover_contain(img: Image.Image, target: tuple[int, int], bg=(255, 255, 255)) -> Image.Image:
    """等比缩放 + 居中留白到目标尺寸（不裁掉内容）。"""
    tw, th = target
    img = img.convert("RGB")
    img.thumbnail((tw, th), Image.LANCZOS)
    canvas = Image.new("RGB", (tw, th), bg)
    canvas.paste(img, ((tw - img.width) // 2, (th - img.height) // 2))
    return canvas


def cover_crop(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    """按目标比例居中裁剪（内容铺满）。"""
    tw, th = target
    img = img.convert("RGB")
    tr = tw / th
    w, h = img.size
    if w / h > tr:
        nw = int(h * tr)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / tr)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return img.resize((tw, th), Image.LANCZOS)


class ImageAdaptService:
    """按平台生成封面/图片规格产物。"""

    @staticmethod
    async def target_ratios(platform: str, owner: Optional[OwnerContext]) -> list[str]:
        cfg = await PlatformRuleConfig.filter(platform=platform, key="cover_ratio", enabled=True).all()
        if cfg:
            val = cfg[0].value
            raw = val.get("value") if isinstance(val, dict) else val
            if isinstance(raw, str) and ":" in raw:
                return [raw]
            if isinstance(raw, list) and raw:
                return [str(x) for x in raw]
        return DEFAULT_RATIOS.get(platform, ["16:9"])

    @staticmethod
    async def adapt_cover(
        source_asset_id: int, platform: str, owner: Optional[OwnerContext],
        uploader_id: Optional[int] = None, mode: str = "crop", watermark: Optional[str] = None,
    ) -> list[dict]:
        """把源封面生成该平台目标比例的 adapted 素材列表。"""
        src = await MediaAsset.get_or_none(id=source_asset_id)
        if not src:
            raise ValueError("源封面素材不存在")
        src_path = MediaService.file_path(src)
        if not src_path.exists():
            raise ValueError("源封面文件不存在")

        ratios = await ImageAdaptService.target_ratios(platform, owner)
        results = []
        with Image.open(src_path) as im:
            for ratio in ratios:
                tw, th = RATIO_SIZE.get(ratio, (1920, 1080))
                out = cover_crop(im, (tw, th)) if mode == "crop" else cover_contain(im, (tw, th))
                if watermark:
                    ImageAdaptService._add_watermark(out, watermark)
                buf = io.BytesIO()
                out.save(buf, format="JPEG", quality=88, optimize=True)
                data = buf.getvalue()
                asset = await MediaService.upload(
                    data=data, content_type="image/jpeg",
                    filename=f"{platform}_{ratio.replace(':', 'x')}.jpg",
                    kind="adapted", owner=owner, content_id=src.content_id,
                    uploader_id=uploader_id,
                    tags=[platform, f"cover-{ratio}"],
                )
                asset["extra"] = asset.get("extra") or {}
                asset["extra"].update({
                    "source_asset_id": source_asset_id, "platform": platform,
                    "ratio": ratio, "width": tw, "height": th, "adapt_mode": mode,
                })
                # 回写 extra
                obj = await MediaAsset.get_or_none(id=asset["id"])
                if obj:
                    obj.extra = asset["extra"]
                    await obj.save(update_fields=["extra"])
                results.append(asset)
        return results

    @staticmethod
    def _add_watermark(img: Image.Image, text: str):
        try:
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", max(16, img.width // 40))
            except Exception:
                font = ImageFont.load_default()
            draw.text((img.width - 220, img.height - 40), text, fill=(255, 255, 255), font=font)
        except Exception:
            pass
