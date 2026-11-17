"""ContentOps 素材链端到端冒烟：建表→上传图片→OCR→封面适配→导出含素材。

运行：.venv/Scripts/python tests/smoke_contentops_media.py
用真实 app lifespan 启动（跑迁移建 media_asset 表），直接调 service 层。
"""
import asyncio
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from base.app_wrapper import real_app
from base.common.authz import OwnerContext

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))


async def main():
    from PIL import Image, ImageDraw, ImageFont
    from base.plugins.contentops.services.media_service import MediaService
    from base.plugins.contentops.services.media_detection_service import MediaDetectionService
    from base.plugins.contentops.services.image_adapt_service import ImageAdaptService
    from base.plugins.contentops.models import MediaAsset, ContentItem, ContentVersion
    from base.plugins.contentops.services.content_service import ContentService
    from base.plugins.contentops.schemas.content_schema import ContentCreate
    from tortoise import Tortoise

    owner = OwnerContext(owner_type="usr", owner_id=990099, data_scope="all",
                         is_superuser=True, org_ids=[], visible_user_ids=None)

    async with real_app.router.lifespan_context(real_app):
        # 1. 表已建成
        conn = Tortoise.get_connection("postgres")
        rows = await conn.execute_query_dict(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='contentops_media_asset'")
        check("media_asset 表已建成", len(rows) > 0)

        # 造一张带文字的测试图
        img = Image.new("RGB", (800, 600), "white")
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 48)
            d.text((40, 260), "PROMO 2026", fill="black", font=font)
        except Exception:
            d.text((40, 260), "PROMO 2026", fill="black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()

        # 2. 上传图片
        asset = await MediaService.upload(
            data=data, content_type="image/png", filename="test.png",
            kind="cover", owner=owner, content_id=None, uploader_id=1,
        )
        check("图片上传成功", asset.get("id") is not None, f"id={asset.get('id')}")
        check("图片尺寸探测", asset.get("width") == 800 and asset.get("height") == 600,
              f"{asset.get('width')}x{asset.get('height')}")
        check("文件真实落盘", (MediaService.file_path(await MediaAsset.get(id=asset['id']))).exists())

        # 3. OCR 提取
        obj = await MediaAsset.get(id=asset["id"])
        result = await MediaDetectionService.extract_text(obj)
        await MediaService.update_ocr(asset["id"], result["text"], result["ocr_status"])
        check("OCR 提取到文字", "PROMO" in result["text"].upper(), f"text={result['text'][:40]!r}")

        # 4. 建源内容并绑定素材
        item = await ContentService.create(
            ContentCreate(title="测试内容", body="<p>正文</p>", summary=None, media=[], topics=["测试"], cover=None),
            owner, creator_id=1,
        )
        await MediaService.bind_to_content([asset["id"]], item["id"], owner)
        obj = await MediaAsset.get(id=asset["id"])
        check("素材绑定到内容", obj.content_id == item["id"])

        # 5. B站双封面适配（16:9 + 4:3）
        adapted = await ImageAdaptService.adapt_cover(asset["id"], "bilibili", owner, uploader_id=1, mode="crop")
        ratios = sorted(a["extra"]["ratio"] for a in adapted)
        check("B站双封面生成", ratios == ["16:9", "4:3"], f"ratios={ratios}")
        adapted_files_ok = True
        for a in adapted:
            aobj = await MediaAsset.get(id=a["id"])
            if not MediaService.file_path(aobj).exists():
                adapted_files_ok = False
        check("适配产物落盘", adapted_files_ok)

        # 6. 构造一个已确认版本 + 导出，验证 ZIP 含素材
        ver = await ContentVersion.create(
            content_id=item["id"], platform="bilibili",
            payload={"title": "测试", "body": "正文", "topics": ["测试"],
                     "cover_asset_id": asset["id"], "adapted_asset_ids": [a["id"] for a in adapted],
                     "cover_ratio": "16:9", "platform": "bilibili"},
            is_adapted=True, confirmed=True, status="confirmed",
            owner_type=owner.owner_type, owner_id=owner.owner_id,
        )
        from base.plugins.contentops.services.export_service import ExportService
        pkg = await ExportService.create_export(
            item["id"], {"bilibili": ver.id}, owner, creator_id=1,
        )
        import zipfile
        zpath = await ExportService.get_download_path(pkg["id"], owner)
        with zipfile.ZipFile(zpath) as zf:
            names = zf.namelist()
        has_cover = any("cover_" in n for n in names if n.endswith((".jpg", ".png")))
        check("导出ZIP含封面素材", has_cover, f"files={[n for n in names if '素材' in n][:3]}")

        # 清理
        await MediaService.cleanup_content_files(item["id"], owner)
        await ContentVersion.filter(content_id=item["id"]).delete()
        await ContentItem.filter(id=item["id"]).delete()
        print("\n[cleanup] 测试数据已清理（含素材文件）")

    passed = sum(1 for _, c in results if c)
    print(f"\n断言总数={len(results)} PASS={passed} FAIL={len(results)-passed}")
    if any(not c for _, c in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
