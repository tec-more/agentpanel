"""
文档版本管理 API 路由
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

try:
    from base.plugins.document.services.document_service import VersionService
    from base.plugins.document.schemas.document_schema import (
        DocumentVersionCreate,
        DocumentVersionUpdate,
        DocumentVersionRollbackRequest,
        DocumentVersionResponse,
        ListResponse,
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

        def post(self, path):
            def decorator(func):
                return func
            return decorator

        def put(self, path):
            def decorator(func):
                return func
            return decorator

        def delete(self, path):
            def decorator(func):
                return func
            return decorator

    class VersionService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def get_by_document(doc_id, **kwargs):
            return [], 0
        @staticmethod
        async def create_version(doc_id, data, user_id=None):
            return None
        @staticmethod
        async def update_version(id, data):
            return None
        @staticmethod
        async def rollback(doc_id, target_version_id, change_log=None, user_id=None):
            return None
        @staticmethod
        async def delete_version(id):
            return False
        @staticmethod
        async def upload_new_version(doc_id, file_bytes, file_name, change_log=None, user_id=None):
            return None, None

    class DocumentVersionCreate(BaseModel): pass
    class DocumentVersionUpdate(BaseModel): pass
    class DocumentVersionRollbackRequest(BaseModel): pass
    class DocumentVersionResponse(BaseModel): pass
    class ListResponse(BaseModel): pass


version_router = APIRouter(prefix="/versions", tags=["文档版本"])


@version_router.get("/document/{document_id}", summary="获取文档版本列表")
async def list_versions(
    document_id: int,
    page: int = 1,
    page_size: int = 20,
    user_id: int = require_permission("document:version")
):
    items, total = await VersionService.get_by_document(document_id, page=page, page_size=page_size)
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@version_router.get("/{version_id}", summary="获取版本详情")
async def get_version(version_id: int, user_id: int = require_permission("document:version")):
    version = await VersionService.get_by_id(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response(data=version)


@version_router.post("/document/{document_id}", summary="为文档创建新版本")
async def create_version(
    document_id: int,
    data: DocumentVersionCreate,
    user_id: int = require_permission("document:version")
):
    try:
        version = await VersionService.create_version(document_id, data, user_id=user_id)
        return success_response(data=version, msg="版本创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@version_router.put("/{version_id}", summary="更新版本信息")
async def update_version(
    version_id: int,
    data: DocumentVersionUpdate,
    user_id: int = require_permission("document:version")
):
    version = await VersionService.update_version(version_id, data)
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response(data=version, msg="版本更新成功")


@version_router.post("/document/{document_id}/rollback", summary="回滚到指定版本")
async def rollback_version(
    document_id: int,
    data: DocumentVersionRollbackRequest,
    user_id: int = require_permission("document:version")
):
    try:
        version = await VersionService.rollback(
            document_id=document_id,
            target_version_id=data.version_id,
            change_log=data.change_log,
            user_id=user_id,
        )
        return success_response(data=version, msg="版本回滚成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@version_router.delete("/{version_id}", summary="删除版本")
async def delete_version(version_id: int, user_id: int = require_permission("document:version")):
    try:
        success = await VersionService.delete_version(version_id)
        if not success:
            raise HTTPException(status_code=404, detail="版本不存在")
        return success_response(msg="版本删除成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@version_router.post("/document/{document_id}/upload", summary="上传新版本文件")
async def upload_new_version(
    document_id: int,
    file: UploadFile = File(...),
    change_log: Optional[str] = Form(None),
    user_id: int = require_permission("document:version")
):
    """上传文件为文档创建新版本"""
    try:
        file_bytes = await file.read()
        file_name = file.filename or "unnamed"

        version, doc = await VersionService.upload_new_version(
            document_id=document_id,
            file_bytes=file_bytes,
            file_name=file_name,
            change_log=change_log,
            user_id=user_id,
        )
        return success_response(
            data={"version": version, "document": doc},
            msg=f"新版本 v{version.version} 上传成功"
        )
    except ValueError as e:
        return fail_response(msg=str(e))
    except Exception as e:
        return fail_response(msg=f"上传失败: {str(e)}")
