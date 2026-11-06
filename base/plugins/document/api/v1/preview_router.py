"""
文档预览与下载 API 路由
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

try:
    from base.plugins.document.services.document_service import (
        DocumentService,
        VersionService,
        PreviewService,
    )
    from base.common.response import success_response, fail_response
    from base.common.permissions import require_permission
except ImportError:
    class BaseModel:
        pass

    class APIRouter:
        def __init__(self, prefix="", tags=None):
            self.prefix = prefix
            self.tags = tags or []

        def get(self, path):
            def decorator(func):
                return func
            return decorator

    class DocumentService:
        @staticmethod
        async def get_by_id(id):
            return None

    class VersionService:
        @staticmethod
        async def get_by_id(id):
            return None

    class PreviewService:
        @staticmethod
        def is_previewable(ft):
            return False
        @staticmethod
        def is_office_file(ft):
            return False
        @staticmethod
        def get_preview_content_type(ft):
            return "application/octet-stream"


preview_router = APIRouter(prefix="/preview", tags=["文档预览"])


@preview_router.get("/{doc_id}", summary="在线预览文档")
async def preview_document(
    doc_id: int,
    inline: bool = True,
    user_id: int = require_permission("document:view")
):
    doc = await DocumentService.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    file_path = doc.file_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if not PreviewService.is_previewable(doc.file_type or ""):
        raise HTTPException(status_code=400, detail="该文件类型不支持在线预览")

    content_type = PreviewService.get_preview_content_type(doc.file_type or "")

    headers = {}
    if not inline:
        headers["Content-Disposition"] = f'attachment; filename="{doc.file_name}"'

    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=doc.file_name if not inline else None,
        headers=headers if not inline else None,
    )


@preview_router.get("/{doc_id}/download", summary="下载文档")
async def download_document(
    doc_id: int,
    user_id: int = require_permission("document:download")
):
    doc = await DocumentService.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    file_path = doc.file_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    content_type = PreviewService.get_preview_content_type(doc.file_type or "")

    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=doc.file_name,
        headers={
            "Content-Disposition": f'attachment; filename="{doc.file_name}"'
        },
    )


@preview_router.get("/{doc_id}/check", summary="检查文档是否可预览")
async def check_preview(
    doc_id: int,
    user_id: int = require_permission("document:view")
):
    doc = await DocumentService.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    file_type = doc.file_type or ""
    is_previewable = PreviewService.is_previewable(file_type)
    is_office = PreviewService.is_office_file(file_type)

    return success_response(data={
        "is_previewable": is_previewable,
        "is_office_file": is_office,
        "file_type": file_type,
        "content_type": PreviewService.get_preview_content_type(file_type),
    })


@preview_router.get("/version/{version_id}", summary="预览指定版本")
async def preview_version(
    version_id: int,
    inline: bool = True,
    user_id: int = require_permission("document:view")
):
    version = await VersionService.get_by_id(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    file_path = version.file_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    doc = await DocumentService.get_by_id(version.document_id)
    file_type = doc.file_type if doc else ""

    if not PreviewService.is_previewable(file_type):
        raise HTTPException(status_code=400, detail="该文件类型不支持在线预览")

    content_type = PreviewService.get_preview_content_type(file_type)

    headers = {}
    if not inline:
        headers["Content-Disposition"] = f'attachment; filename="v{version.version}_{doc.file_name if doc else ""}"'

    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=f"v{version.version}_{doc.file_name}" if not inline and doc else None,
        headers=headers if not inline else None,
    )


@preview_router.get("/version/{version_id}/download", summary="下载指定版本")
async def download_version(
    version_id: int,
    user_id: int = require_permission("document:download")
):
    version = await VersionService.get_by_id(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    file_path = version.file_path
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    doc = await DocumentService.get_by_id(version.document_id)
    file_type = doc.file_type if doc else ""
    content_type = PreviewService.get_preview_content_type(file_type)

    filename = f"v{version.version}_{doc.file_name}" if doc else f"v{version.version}_file"

    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
