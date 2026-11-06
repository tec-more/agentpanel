"""
文档管理 API 路由 - 主文档 CRUD
"""
import os
from typing import Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel

try:
    from base.plugins.document.services.document_service import (
        DocumentService,
        _generate_storage_path,
        _extract_file_extension,
    )
    from base.plugins.document.schemas.document_schema import (
        DocumentCreate,
        DocumentUpdate,
        DocumentResponse,
        DocumentListQuery,
        DocumentMoveRequest,
        DocumentRestoreRequest,
        DocumentDeleteRequest,
    )
    from base.plugins.document.services.rag_integration_service import RAGIntegrationService
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

    class DocumentService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def get_list(**kwargs):
            return [], 0
        @staticmethod
        async def create_document(data, user_id=None, file_bytes=None):
            return None
        @staticmethod
        async def update_document(id, data, user_id=None):
            return None
        @staticmethod
        async def soft_delete(id):
            return False
        @staticmethod
        async def batch_soft_delete(ids):
            return 0
        @staticmethod
        async def restore(id):
            return False
        @staticmethod
        async def batch_restore(ids):
            return 0
        @staticmethod
        async def permanent_delete(id):
            return False
        @staticmethod
        async def move_to_category(id, target_id):
            return None
        @staticmethod
        async def get_by_business(bt, bid):
            return []
        @staticmethod
        async def get_trash_list(**kwargs):
            return [], 0
        @staticmethod
        async def get_statistics():
            return {}

    def _generate_storage_path(name):
        return ""
    def _extract_file_extension(name):
        return ""

    class DocumentCreate(BaseModel): pass
    class DocumentUpdate(BaseModel): pass
    class DocumentResponse(BaseModel): pass
    class DocumentListQuery(BaseModel): pass
    class DocumentMoveRequest(BaseModel): pass
    class DocumentRestoreRequest(BaseModel): pass
    class DocumentDeleteRequest(BaseModel): pass

    class RAGIntegrationService:
        @staticmethod
        async def auto_link_on_upload(*args, **kwargs):
            return {"status": "skipped", "message": "RAG 集成服务未加载"}
        @staticmethod
        async def link_to_knowledge_base(*args, **kwargs):
            return None


document_router = APIRouter(prefix="/documents", tags=["文档管理"])


@document_router.post("", summary="创建文档(元数据)")
async def create_document(data: DocumentCreate, user_id: int = require_permission("document:upload")):
    try:
        doc = await DocumentService.create_document(data, user_id=user_id)
        return success_response(data=doc, msg="文档创建成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@document_router.post("/upload", summary="上传文档文件(可选择关联RAG知识库)")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    business_type: Optional[str] = Form(None),
    business_id: Optional[int] = Form(None),
    visibility: str = Form("private"),
    knowledge_base_id: Optional[int] = Form(None),
    user_id: int = require_permission("document:upload")
):
    """上传企业文档，可选一步关联 RAG 知识库

    集成顺序：企业文档先创建 → 可选关联 RAG
    """
    try:
        file_bytes = await file.read()
        file_name = file.filename or "unnamed"
        file_ext = _extract_file_extension(file_name)

        storage_path = _generate_storage_path(file_name)
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        with open(storage_path, "wb") as f:
            f.write(file_bytes)

        doc = DocumentCreate(
            title=title or os.path.splitext(file_name)[0],
            file_name=file_name,
            file_type=file_ext,
            file_size=len(file_bytes),
            file_path=storage_path,
            category_id=category_id,
            status="normal",
            description=description,
            business_type=business_type,
            business_id=business_id,
            visibility=visibility,
        )

        result = await DocumentService.create_document(doc, user_id=user_id, file_bytes=None)

        if knowledge_base_id:
            try:
                rag_result = await RAGIntegrationService.auto_link_on_upload(
                    doc_id=result.id,
                    file_path=storage_path,
                    file_name=file_name,
                    knowledge_base_id=knowledge_base_id,
                    user_id=user_id,
                )
                result_data = {
                    "document": result,
                    "rag_link": rag_result,
                }
                return success_response(data=result_data, msg="文档上传成功并已关联 RAG 知识库")
            except Exception as rag_e:
                result_data = {
                    "document": result,
                    "rag_link": {"status": "failed", "error": str(rag_e)},
                }
                return success_response(data=result_data, msg="文档上传成功，但 RAG 关联失败")

        return success_response(data=result, msg="文档上传成功")
    except Exception as e:
        return fail_response(msg=f"文档上传失败: {str(e)}")


@document_router.get("", summary="获取文档列表")
async def list_documents(
    page: int = 1,
    page_size: int = 10,
    title: Optional[str] = None,
    file_name: Optional[str] = None,
    file_type: Optional[str] = None,
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    business_type: Optional[str] = None,
    business_id: Optional[int] = None,
    visibility: Optional[str] = None,
    tag: Optional[str] = None,
    user_id: int = require_permission("document:view")
):
    items, total = await DocumentService.get_list(
        page=page, page_size=page_size,
        title=title, file_name=file_name, file_type=file_type,
        category_id=category_id, status=status,
        business_type=business_type, business_id=business_id,
        visibility=visibility, tag=tag,
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@document_router.get("/statistics", summary="获取文档统计信息")
async def get_statistics(user_id: int = require_permission("document:view")):
    stats = await DocumentService.get_statistics()
    return success_response(data=stats)


@document_router.get("/trash", summary="获取回收站文档列表")
async def list_trash(
    page: int = 1,
    page_size: int = 10,
    title: Optional[str] = None,
    user_id: int = require_permission("document:view")
):
    items, total = await DocumentService.get_trash_list(page=page, page_size=page_size, title=title)
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@document_router.get("/business/{business_type}/{business_id}", summary="按业务类型查询关联文档")
async def get_by_business(
    business_type: str,
    business_id: int,
    user_id: int = require_permission("document:view")
):
    items = await DocumentService.get_by_business(business_type, business_id)
    return success_response(data=items)


@document_router.get("/{doc_id}", summary="获取文档详情")
async def get_document(doc_id: int, user_id: int = require_permission("document:view")):
    doc = await DocumentService.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return success_response(data=doc)


@document_router.put("/{doc_id}", summary="更新文档")
async def update_document(
    doc_id: int,
    data: DocumentUpdate,
    user_id: int = require_permission("document:edit")
):
    try:
        doc = await DocumentService.update_document(doc_id, data, user_id=user_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        return success_response(data=doc, msg="文档更新成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@document_router.delete("/{doc_id}", summary="删除文档(软删除)")
async def delete_document(doc_id: int, user_id: int = require_permission("document:delete")):
    success = await DocumentService.soft_delete(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return success_response(msg="文档已移入回收站")


@document_router.post("/batch-delete", summary="批量删除文档(软删除)")
async def batch_delete(data: DocumentDeleteRequest, user_id: int = require_permission("document:delete")):
    count = await DocumentService.batch_soft_delete(data.document_ids)
    return success_response(data={"deleted_count": count}, msg=f"已删除 {count} 个文档")


@document_router.post("/batch-restore", summary="批量恢复文档")
async def batch_restore(data: DocumentRestoreRequest, user_id: int = require_permission("document:trash:manage")):
    count = await DocumentService.batch_restore(data.document_ids)
    return success_response(data={"restored_count": count}, msg=f"已恢复 {count} 个文档")


@document_router.delete("/{doc_id}/permanent", summary="永久删除文档")
async def permanent_delete(doc_id: int, user_id: int = require_permission("document:trash:manage")):
    success = await DocumentService.permanent_delete(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return success_response(msg="文档已永久删除")


@document_router.post("/{doc_id}/move", summary="移动文档到其他分类")
async def move_document(
    doc_id: int,
    data: DocumentMoveRequest,
    user_id: int = require_permission("document:edit")
):
    try:
        doc = await DocumentService.move_to_category(doc_id, data.target_category_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        return success_response(data=doc, msg="文档移动成功")
    except ValueError as e:
        return fail_response(msg=str(e))
