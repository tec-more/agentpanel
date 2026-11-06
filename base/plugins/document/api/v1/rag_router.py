"""
文档 RAG 集成 API 路由
================================
集成顺序：企业文档为主 → RAG 为辅

流程A: 企业文档 → RAG（正向主流程）
  - /documents/{id}/link         关联单个文档到知识库
  - /documents/batch-link        批量关联文档到知识库
  - /documents/{id}/reprocess    重新处理已关联文档

流程B: RAG → 企业文档（反向同步）
  - /rag-documents/{id}/sync     单个 RAG 文档同步到文档模块
  - /rag-documents/batch-sync    批量 RAG 文档同步到文档模块
"""
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
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

    class RAGIntegrationService:
        @staticmethod
        async def link_to_knowledge_base(*args, **kwargs):
            return None
        @staticmethod
        async def batch_link_to_knowledge_base(*args, **kwargs):
            return {}
        @staticmethod
        async def auto_link_on_upload(*args, **kwargs):
            return None
        @staticmethod
        async def sync_from_rag(*args, **kwargs):
            return None
        @staticmethod
        async def batch_sync_from_rag(*args, **kwargs):
            return {}
        @staticmethod
        async def unlink_from_knowledge_base(*args, **kwargs):
            return None
        @staticmethod
        async def get_linked_documents(*args, **kwargs):
            return []
        @staticmethod
        async def reprocess_document(*args, **kwargs):
            return None


rag_router = APIRouter(tags=["RAG 集成"])


class LinkRequest(BaseModel):
    knowledge_base_id: int
    user_id: Optional[int] = None


class BatchLinkRequest(BaseModel):
    document_ids: List[int]
    knowledge_base_id: int
    user_id: Optional[int] = None


class UnlinkRequest(BaseModel):
    user_id: Optional[int] = None


class ReprocessRequest(BaseModel):
    user_id: Optional[int] = None


class SyncFromRagRequest(BaseModel):
    user_id: Optional[int] = None


class BatchSyncFromRagRequest(BaseModel):
    rag_document_ids: List[int]
    user_id: Optional[int] = None


# ==================== 流程A: 企业文档 → RAG ====================

@rag_router.post("/documents/{document_id}/link", summary="关联文档到 RAG 知识库（企业文档先→RAG）")
async def link_document_to_rag(
    document_id: int,
    data: LinkRequest,
    user_id: int = require_permission("document:edit")
):
    """将已存在的企业文档关联到 RAG 知识库

    集成顺序：企业文档 → RAG
    """
    try:
        result = await RAGIntegrationService.link_to_knowledge_base(
            document_id=document_id,
            knowledge_base_id=data.knowledge_base_id,
            user_id=user_id,
        )
        status = result.get("status", "")
        if status in ("linked", "linked_processing_failed", "already_linked"):
            msg_map = {
                "linked": "文档已关联到知识库并处理成功",
                "linked_processing_failed": "文档已关联，但 RAG 处理失败",
                "already_linked": "文档已关联到该知识库",
            }
            return success_response(data=result, msg=msg_map.get(status, "操作成功"))
        else:
            return fail_response(msg=f"关联失败: {result.get('error', '未知错误')}")
    except ValueError as e:
        return fail_response(msg=str(e))


@rag_router.post("/documents/batch-link", summary="批量关联文档到 RAG 知识库")
async def batch_link_documents_to_rag(
    data: BatchLinkRequest,
    user_id: int = require_permission("document:edit")
):
    """批量将企业文档关联到 RAG 知识库

    集成顺序：企业文档批量 → RAG 批量
    """
    try:
        result = await RAGIntegrationService.batch_link_to_knowledge_base(
            document_ids=data.document_ids,
            knowledge_base_id=data.knowledge_base_id,
            user_id=user_id,
        )
        return success_response(data=result, msg=f"批量关联完成: 成功{result['success_count']}, 失败{result['fail_count']}")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.post("/documents/{document_id}/reprocess", summary="重新处理已关联文档")
async def reprocess_document(
    document_id: int,
    data: Optional[ReprocessRequest] = None,
    user_id: int = require_permission("document:edit")
):
    """重新触发文档的 RAG 分块与向量化"""
    try:
        result = await RAGIntegrationService.reprocess_document(
            document_id=document_id,
            user_id=user_id,
        )
        return success_response(data=result, msg="文档已重新处理")
    except ValueError as e:
        return fail_response(msg=str(e))


# ==================== 流程B: RAG → 企业文档 ====================

@rag_router.post("/rag-documents/{rag_document_id}/sync", summary="RAG 文档反向同步到企业文档")
async def sync_rag_document_to_document(
    rag_document_id: int,
    data: Optional[SyncFromRagRequest] = None,
    user_id: int = require_permission("document:upload")
):
    """将 RAG 模块的文档反向同步到企业文档管理模块

    集成顺序：RAG 文档 → 企业文档（反向）
    """
    try:
        result = await RAGIntegrationService.sync_from_rag(
            rag_document_id=rag_document_id,
            user_id=user_id,
        )
        status = result.get("status", "")
        if status == "synced":
            return success_response(data=result, msg="已同步到企业文档模块")
        elif status == "already_synced":
            return success_response(data=result, msg="文档已存在于企业文档模块")
        elif status == "skipped_already_from_document":
            return success_response(data=result, msg="该文档源自企业文档模块，无需同步")
        else:
            return success_response(data=result, msg=result.get("status", "未知状态"))
    except ValueError as e:
        return fail_response(msg=str(e))


@rag_router.post("/rag-documents/batch-sync", summary="批量 RAG 文档反向同步到企业文档")
async def batch_sync_rag_documents(
    data: BatchSyncFromRagRequest,
    user_id: int = require_permission("document:upload")
):
    """批量将 RAG 文档反向同步到企业文档管理模块"""
    try:
        result = await RAGIntegrationService.batch_sync_from_rag(
            rag_document_ids=data.rag_document_ids,
            user_id=user_id,
        )
        return success_response(data=result, msg=f"批量同步完成: 成功{result['success_count']}, 跳过{result['skip_count']}")
    except Exception as e:
        return fail_response(msg=str(e))


# ==================== 查询与解绑 ====================

@rag_router.post("/documents/{document_id}/unlink", summary="取消文档与 RAG 的关联")
async def unlink_document_from_rag(
    document_id: int,
    data: Optional[UnlinkRequest] = None,
    user_id: int = require_permission("document:edit")
):
    """取消关联（保留企业文档，仅移除 RAG 副本）"""
    try:
        result = await RAGIntegrationService.unlink_from_knowledge_base(
            document_id=document_id,
        )
        return success_response(data=result, msg="已取消关联")
    except ValueError as e:
        return fail_response(msg=str(e))


@rag_router.get("/knowledge-bases/{knowledge_base_id}/documents", summary="获取知识库关联的企业文档")
async def get_linked_documents(
    knowledge_base_id: int,
    user_id: int = require_permission("document:view")
):
    """获取指定知识库关联的所有企业文档列表"""
    try:
        docs = await RAGIntegrationService.get_linked_documents(knowledge_base_id)
        return success_response(data=docs)
    except Exception as e:
        return fail_response(msg=str(e))
