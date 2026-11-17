"""素材库路由：上传/列表/下载/删除/OCR/图片适配。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse

from base.common.authz import OwnerContext, require_owner
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.contentops.services.media_service import MediaService
from base.plugins.contentops.services.media_detection_service import MediaDetectionService
from base.plugins.contentops.services.image_adapt_service import ImageAdaptService

media_router = APIRouter(prefix="/media", tags=["素材库"])


@media_router.post("/upload", summary="上传素材（图片/封面/视频）")
async def upload_media(
    file: UploadFile = File(...),
    kind: str = Form("image", description="image/cover/video"),
    content_id: Optional[int] = Form(None),
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:content:edit"),
):
    if kind not in ("image", "cover", "video"):
        return fail_response(msg="kind 只能是 image/cover/video", code=400)
    try:
        data = await file.read()
        result = await MediaService.upload(
            data=data, content_type=file.content_type or "", filename=file.filename or "",
            kind=kind, owner=owner, content_id=content_id, uploader_id=user_id,
        )
        return success_response(data=result, msg="上传成功")
    except ValueError as e:
        return fail_response(msg=str(e), code=400)


@media_router.get("", summary="素材列表")
async def list_media(
    content_id: Optional[int] = None, kind: Optional[str] = None,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:content:view"),
):
    return success_response(data={"items": await MediaService.list_assets(owner, content_id, kind)})


@media_router.get("/file/{asset_id}", summary="下载/访问素材文件")
async def get_media_file(
    asset_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:content:view"),
):
    try:
        asset = await MediaService.get_file_asset(asset_id, owner)
        path = MediaService.file_path(asset)
        if not path.exists():
            return fail_response(msg="文件不存在", code=404)
        return FileResponse(path, media_type=asset.content_type, filename=asset.filename)
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@media_router.delete("/{asset_id}", summary="删除素材")
async def delete_media(
    asset_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:content:edit"),
):
    try:
        await MediaService.delete_asset(asset_id, owner)
        return success_response(msg="已删除")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@media_router.post("/{asset_id}/extract", summary="提取素材文字（OCR/ASR）")
async def extract_text(
    asset_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:compliance:check"),
):
    try:
        asset = await MediaService.get_file_asset(asset_id, owner)
        result = await MediaDetectionService.extract_text(asset)
        # 缓存到素材记录
        await MediaService.update_ocr(asset_id, result["text"], result["ocr_status"])
        return success_response(data=result, msg="提取完成")
    except ValueError as e:
        return fail_response(msg=str(e), code=400)


@media_router.post("/{asset_id}/adapt-cover", summary="生成平台封面适配产物")
async def adapt_cover(
    asset_id: int, platform: str = Query(..., description="目标平台"),
    mode: str = Query("crop", description="crop 裁剪 / contain 留白"),
    watermark: Optional[str] = Query(None, description="水印文字"),
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_permission("contentops:adapt:generate"),
):
    try:
        results = await ImageAdaptService.adapt_cover(
            asset_id, platform, owner, uploader_id=user_id, mode=mode, watermark=watermark,
        )
        return success_response(data={"items": results}, msg="封面适配完成")
    except ValueError as e:
        return fail_response(msg=str(e), code=400)
