"""成品导出服务：按平台打包 + ZIP 下载 + 发布须知 + 导出快照。"""
import io
import json
import zipfile
from pathlib import Path
from typing import Optional

from base.common.authz import OwnerContext, get_owned_or_404, owned_queryset
from base.plugins.contentops.models import ContentItem, ContentVersion, ExportPackage, PublishLedger

# services -> contentops -> plugins -> base -> 项目根
STORAGE_ROOT = Path(__file__).resolve().parents[4] / "storage" / "contentops"


def _platform_notice(platform: str, payload: dict) -> str:
    """生成发布须知（话题/@/格式提示）。"""
    lines = [f"# {platform} 发布须知", ""]
    topics = payload.get("topics") or []
    if topics:
        lines.append("话题标签：" + " ".join(f"#{t}#" for t in topics))
    ratio = payload.get("cover_ratio")
    if ratio:
        lines.append(f"封面比例：{ratio}")
    if platform == "bilibili":
        lines.append("需选择一级+二级分区；建议声明原创；封面需同时上传 16:9 与 4:3 两个比例。")
        lines.append("标签最多 10 个、话题最多 1 个。")
    if platform == "douyin":
        lines.append("成片为竖屏 9:16；标题短、避免引流词。")
    if platform == "xiaohongshu":
        lines.append("标题钩子 + emoji 风格；避免硬广与导流。")
    lines.append("")
    lines.append("本内容由系统生成，请人工复核后发布。")
    return "\n".join(lines)


class ExportService:
    """成品导出服务。"""

    @staticmethod
    async def create_export(
        content_id: int, platform_version_ids: dict[str, int],
        owner: Optional[OwnerContext], creator_id: Optional[int] = None,
    ) -> dict:
        """打包导出：校验所有版本已确认，生成 ZIP，落导出快照 + 台账。"""
        item = await get_owned_or_404(ContentItem, content_id, owner) if owner else await ContentItem.get_or_none(id=content_id)
        if not item:
            raise ValueError("源内容不存在或无权导出")

        versions = []
        for platform, vid in platform_version_ids.items():
            ver = await get_owned_or_404(ContentVersion, vid, owner) if owner else await ContentVersion.get_or_none(id=vid)
            if not ver or ver.content_id != content_id:
                raise ValueError(f"成品版本 {vid} 不存在或不属于该内容")
            if not ver.confirmed:
                raise ValueError(f"【{platform}】成品尚未人工确认，禁止导出")
            # 导出前再校验 P0
            from base.plugins.contentops.models import ComplianceHit
            has_p0 = await ComplianceHit.filter(content_version_id=vid, level="P0", confirmed=False).exists()
            if has_p0:
                raise ValueError(f"【{platform}】存在未处置的 P0 高危命中，禁止导出")
            versions.append((platform, ver))

        # 生成 ZIP（内存）：文案 + 封面 + 正文图 + 成片 + 发布须知
        from base.plugins.contentops.models import MediaAsset
        from base.plugins.contentops.services.media_service import MediaService

        buf = io.BytesIO()
        file_keys: dict[str, list[str]] = {}
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for platform, ver in versions:
                payload = ver.payload
                base = f"{platform}/"
                media_dir = base + "素材/"
                title = payload.get("title", "")
                body = payload.get("body", "")
                names = [
                    base + "文案.md", base + "文案.txt",
                    base + "发布须知.md", base + "meta.json",
                ]
                zf.writestr(names[0], f"# {title}\n\n{body}\n")
                zf.writestr(names[1], f"{title}\n\n{body}\n")
                zf.writestr(names[2], _platform_notice(platform, payload))
                zf.writestr(names[3], json.dumps(payload, ensure_ascii=False, indent=2, default=str))

                # 把引用的素材文件真正打进包：封面 / 正文图 / 成片
                # 引用约定：payload.cover_asset_id / image_asset_ids / video_asset_id / adapted_asset_ids
                ref_ids: list[int] = []
                for key in ("cover_asset_id", "video_asset_id"):
                    v = payload.get(key)
                    if isinstance(v, int):
                        ref_ids.append(v)
                for key in ("image_asset_ids", "adapted_asset_ids"):
                    v = payload.get(key)
                    if isinstance(v, list):
                        ref_ids.extend(x for x in v if isinstance(x, int))
                seen = set()
                for aid in ref_ids:
                    if aid in seen:
                        continue
                    seen.add(aid)
                    asset = await MediaAsset.get_or_none(id=aid)
                    if not asset:
                        continue
                    src = MediaService.file_path(asset)
                    if not src.exists():
                        continue
                    arcname = f"{media_dir}{asset.kind}_{aid}_{asset.filename}"
                    zf.write(src, arcname)
                    names.append(arcname)
                file_keys[platform] = names
        buf.seek(0)

        # 落盘
        pkg = await ExportPackage.create(
            content_id=content_id,
            platforms=list(platform_version_ids.keys()),
            version_ids=list(platform_version_ids.values()),
            file_keys=file_keys,
            rule_version=versions[0][1].rule_version if versions else None,
            owner_type=owner.owner_type if owner else "usr",
            owner_id=owner.owner_id if owner else None,
            creator_id=creator_id,
        )
        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        zip_path = STORAGE_ROOT / f"export_{pkg.id}.zip"
        zip_path.write_bytes(buf.getvalue())

        # 生成台账待发布记录
        for platform, ver in versions:
            await PublishLedger.create(
                version_id=ver.id, platform=platform, status="pending",
                owner_type=owner.owner_type if owner else "usr",
                owner_id=owner.owner_id if owner else None,
            )

        return await pkg.to_dict()

    @staticmethod
    async def get_download_path(package_id: int, owner: Optional[OwnerContext]) -> Path:
        pkg = await get_owned_or_404(ExportPackage, package_id, owner) if owner else await ExportPackage.get_or_none(id=package_id)
        if not pkg:
            raise ValueError("导出包不存在或无权访问")
        path = STORAGE_ROOT / f"export_{pkg.id}.zip"
        if not path.exists():
            raise ValueError("导出文件已丢失")
        return path

    @staticmethod
    async def list_exports(owner: Optional[OwnerContext]):
        qs = owned_queryset(ExportPackage, owner) if owner else ExportPackage.all()
        rows = await qs.order_by("-created_at")
        return [await r.to_dict() for r in rows]
