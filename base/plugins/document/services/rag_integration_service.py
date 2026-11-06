"""
文档管理 RAG 集成服务
================================
设计原则：企业文档为主，RAG 为辅

集成顺序：
  流程A（正向主流程）：企业文档 → RAG
    1. 用户先创建/上传企业文档到文档管理模块
    2. 上传时可选择关联 RAG 知识库（一步完成）
    3. 系统自动将文档同步到 RAG 并触发处理

  流程B（反向同步）：RAG → 企业文档
    1. 用户直接在 RAG 模块上传文档
    2. 可将 RAG 文档反向同步到文档管理模块
    3. 文档模块成为统一入口

核心规则：
  - 文档管理模块是"源头"（source of truth）
  - RAG 是"处理层"（processing layer）
  - 所有文档元数据以文档管理模块为准
  - RAG 中的文档通过 metadata 关联回文档管理模块
"""
import os
import logging
import io
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import UploadFile

logger = logging.getLogger(__name__)

RAG_BUSINESS_TYPE = "rag_knowledge_base"


class RAGIntegrationService:
    """RAG 知识库集成服务"""

    # ==================== 流程A: 企业文档 → RAG (正向主流程) ====================

    @staticmethod
    async def link_to_knowledge_base(
        document_id: int,
        knowledge_base_id: int,
        user_id: Optional[int] = None
    ) -> Optional[dict]:
        """将已存在的企业文档关联到 RAG 知识库（标准流程）

        顺序：企业文档先 → 再关联 RAG
        """
        from base.plugins.document.models.document_models import Document

        doc = await Document.filter(id=document_id).first()
        if not doc:
            raise ValueError("文档不存在")

        doc.business_type = RAG_BUSINESS_TYPE
        doc.business_id = knowledge_base_id
        await doc.save()

        logger.info(f"文档 {doc.id} 已关联到知识库 {knowledge_base_id}")

        try:
            rag_result = await RAGIntegrationService._sync_to_rag(doc, user_id)
            return {
                "document_id": doc.id,
                "rag_document_id": rag_result.get("rag_document_id"),
                "knowledge_base_id": knowledge_base_id,
                "status": rag_result.get("status", "linked"),
                "message": rag_result.get("message"),
            }
        except Exception as e:
            logger.error(f"RAG 同步失败: {e}")
            return {
                "document_id": doc.id,
                "rag_document_id": None,
                "knowledge_base_id": knowledge_base_id,
                "status": "link_failed",
                "error": str(e),
            }

    @staticmethod
    async def batch_link_to_knowledge_base(
        document_ids: List[int],
        knowledge_base_id: int,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """批量将企业文档关联到 RAG 知识库"""
        results = []
        success_count = 0
        fail_count = 0

        for doc_id in document_ids:
            try:
                result = await RAGIntegrationService.link_to_knowledge_base(
                    document_id=doc_id,
                    knowledge_base_id=knowledge_base_id,
                    user_id=user_id,
                )
                if result.get("status") in ("linked", "linked_processing_failed"):
                    success_count += 1
                else:
                    fail_count += 1
                results.append(result)
            except Exception as e:
                fail_count += 1
                results.append({
                    "document_id": doc_id,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "total": len(document_ids),
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results,
        }

    @staticmethod
    async def auto_link_on_upload(
        doc_id: int,
        file_path: str,
        file_name: str,
        knowledge_base_id: int,
        user_id: Optional[int] = None
    ) -> Optional[dict]:
        """上传文档时自动关联 RAG（一步完成）

        顺序：上传企业文档的同时 → 立即触发 RAG 关联
        """
        from base.plugins.document.models.document_models import Document

        doc = await Document.filter(id=doc_id).first()
        if not doc:
            raise ValueError("文档不存在")

        if doc.business_type == RAG_BUSINESS_TYPE:
            logger.info(f"文档 {doc_id} 已关联到知识库 {doc.business_id}，跳过")
            return {
                "document_id": doc.id,
                "status": "already_linked",
                "knowledge_base_id": doc.business_id,
            }

        doc.business_type = RAG_BUSINESS_TYPE
        doc.business_id = knowledge_base_id
        await doc.save()

        try:
            rag_result = await RAGIntegrationService._sync_to_rag(doc, user_id)
            return {
                "document_id": doc.id,
                "rag_document_id": rag_result.get("rag_document_id"),
                "knowledge_base_id": knowledge_base_id,
                "status": rag_result.get("status", "linked"),
                "message": rag_result.get("message"),
            }
        except Exception as e:
            logger.error(f"自动关联 RAG 失败: {e}")
            return {
                "document_id": doc.id,
                "rag_document_id": None,
                "knowledge_base_id": knowledge_base_id,
                "status": "link_failed",
                "error": str(e),
            }

    # ==================== 流程B: RAG → 企业文档 (反向同步) ====================

    @staticmethod
    async def sync_from_rag(
        rag_document_id: int,
        user_id: Optional[int] = None
    ) -> Optional[dict]:
        """将 RAG 文档反向同步到企业文档管理模块

        顺序：RAG 文档先 → 反向创建企业文档记录
        """
        from base.plugins.agent.models.rag import RAGDocument
        from base.plugins.document.models.document_models import Document

        rag_doc = await RAGDocument.filter(id=rag_document_id).first()
        if not rag_doc:
            raise ValueError("RAG 文档不存在")

        metadata = getattr(rag_doc, "metadata", {}) or {}
        if metadata.get("source") == "document_module":
            logger.info(f"RAG 文档 {rag_document_id} 源自文档模块，无需反向同步")
            return {
                "rag_document_id": rag_document_id,
                "status": "skipped_already_from_document",
            }

        existing_doc_id = metadata.get("document_id")
        if existing_doc_id:
            existing = await Document.filter(id=existing_doc_id).first()
            if existing:
                return {
                    "rag_document_id": rag_document_id,
                    "document_id": existing.id,
                    "status": "already_synced",
                }

        title = rag_doc.title or Path(rag_doc.file_name or "unknown").stem
        file_name = rag_doc.file_name or f"rag_{rag_document_id}.txt"

        local_path = None
        if rag_doc.file_path and os.path.exists(rag_doc.file_path):
            local_path = rag_doc.file_path
        else:
            local_path = await RAGIntegrationService._save_rag_content_locally(rag_doc)

        doc = await Document.create(
            title=title,
            file_name=file_name,
            file_type=rag_doc.file_type,
            file_size=rag_doc.file_size or 0,
            file_path=local_path or rag_doc.file_path or "",
            status="normal",
            description=f"从 RAG 知识库同步 (KB: {rag_doc.knowledge_base_id})",
            business_type=RAG_BUSINESS_TYPE,
            business_id=rag_doc.knowledge_base_id,
            visibility="private",
            created_by_id=user_id,
        )

        metadata["source"] = "rag_module"
        metadata["document_id"] = doc.id
        rag_doc.metadata = metadata
        await rag_doc.save()

        logger.info(f"RAG 文档 {rag_document_id} 已反向同步为企业文档 {doc.id}")

        return {
            "rag_document_id": rag_document_id,
            "document_id": doc.id,
            "knowledge_base_id": rag_doc.knowledge_base_id,
            "status": "synced",
        }

    @staticmethod
    async def batch_sync_from_rag(
        rag_document_ids: List[int],
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """批量将 RAG 文档反向同步到企业文档管理模块"""
        results = []
        success_count = 0
        skip_count = 0

        for rag_id in rag_document_ids:
            try:
                result = await RAGIntegrationService.sync_from_rag(
                    rag_document_id=rag_id,
                    user_id=user_id,
                )
                if result.get("status") == "synced":
                    success_count += 1
                else:
                    skip_count += 1
                results.append(result)
            except Exception as e:
                results.append({
                    "rag_document_id": rag_id,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "total": len(rag_document_ids),
            "success_count": success_count,
            "skip_count": skip_count,
            "results": results,
        }

    # ==================== 解绑与查询 ====================

    @staticmethod
    async def unlink_from_knowledge_base(document_id: int) -> Optional[dict]:
        """取消文档与 RAG 知识库的关联（保留企业文档，仅移除 RAG 副本）"""
        from base.plugins.document.models.document_models import Document

        doc = await Document.filter(id=document_id).first()
        if not doc:
            raise ValueError("文档不存在")

        if doc.business_type != RAG_BUSINESS_TYPE:
            raise ValueError("该文档未关联 RAG 知识库")

        kb_id = doc.business_id
        doc.business_type = None
        doc.business_id = None
        await doc.save()

        try:
            from base.plugins.agent.models.rag import RAGDocument
            all_docs = await RAGDocument.filter(knowledge_base_id=kb_id).all()
            deleted_count = 0
            for rd in all_docs:
                meta = getattr(rd, "metadata", {}) or {}
                if meta.get("document_id") == document_id:
                    await rd.delete()
                    deleted_count += 1
            logger.info(f"已取消关联，删除 {deleted_count} 条 RAG 文档副本")
        except Exception as e:
            logger.warning(f"清理 RAG 文档副本失败: {e}")

        return {
            "document_id": doc.id,
            "knowledge_base_id": kb_id,
            "status": "unlinked",
            "note": "企业文档已保留，仅移除 RAG 副本",
        }

    @staticmethod
    async def get_linked_documents(knowledge_base_id: int) -> List[dict]:
        """获取已关联到指定知识库的企业文档列表"""
        from base.plugins.document.models.document_models import Document

        docs = await Document.filter(
            business_type=RAG_BUSINESS_TYPE,
            business_id=knowledge_base_id,
            status="normal",
        ).order_by("-created_at")

        return [
            {
                "document_id": doc.id,
                "title": doc.title,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "version": doc.version,
                "status": doc.status,
                "created_at": str(doc.created_at) if doc.created_at else None,
            }
            for doc in docs
        ]

    @staticmethod
    async def reprocess_document(
        document_id: int,
        user_id: Optional[int] = None
    ) -> Optional[dict]:
        """重新处理已关联文档（重新分块和向量化）"""
        from base.plugins.document.models.document_models import Document
        from base.plugins.agent.services.rag_service import RAGService
        from base.plugins.agent.models.rag import RAGDocument

        doc = await Document.filter(id=document_id).first()
        if not doc:
            raise ValueError("文档不存在")

        if doc.business_type != RAG_BUSINESS_TYPE:
            raise ValueError("该文档未关联 RAG 知识库")

        try:
            rag_docs = await RAGDocument.filter(knowledge_base_id=doc.business_id).all()
            target_rag_doc = None
            for rd in rag_docs:
                meta = getattr(rd, "metadata", {}) or {}
                if meta.get("document_id") == doc.id:
                    target_rag_doc = rd
                    break

            if not target_rag_doc:
                return await RAGIntegrationService._sync_to_rag(doc, user_id)

            await RAGService.process_document(target_rag_doc.id, user_id=user_id)
            return {
                "document_id": doc.id,
                "rag_document_id": target_rag_doc.id,
                "status": "reprocessed",
            }
        except ImportError as e:
            raise ValueError(f"RAG 模块未安装: {e}")
        except Exception as e:
            logger.error(f"重新处理文档失败: {e}")
            raise

    # ==================== 内部方法 ====================

    @staticmethod
    async def _sync_to_rag(doc, user_id: Optional[int] = None) -> dict:
        """将企业文档同步到 RAG 知识库"""
        from base.plugins.agent.services.rag_service import RAGService

        file_path = doc.file_path
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")

        with open(file_path, "rb") as f:
            file_content = f.read()

        upload_file = UploadFile(
            filename=doc.file_name,
            file=io.BytesIO(file_content),
            headers={"content-type": "application/octet-stream"},
        )

        rag_doc = await RAGService.upload_document(
            knowledge_base_id=doc.business_id,
            file=upload_file,
            user_id=user_id,
        )

        metadata = getattr(rag_doc, "metadata", {}) or {}
        metadata["source"] = "document_module"
        metadata["document_id"] = doc.id

        rag_doc.metadata = metadata
        await rag_doc.save()

        logger.info(f"企业文档 {doc.id} 已同步到 RAG 文档 {rag_doc.id}")

        try:
            await RAGService.process_document(rag_doc.id, user_id=user_id)
            logger.info(f"RAG 文档 {rag_doc.id} 处理完成")
            return {"rag_document_id": rag_doc.id, "status": "linked", "message": "上传并处理成功"}
        except Exception as e:
            logger.warning(f"RAG 文档处理失败（已创建）: {e}")
            return {
                "rag_document_id": rag_doc.id,
                "status": "linked_processing_failed",
                "message": f"上传成功，但处理失败: {str(e)}",
            }

    @staticmethod
    async def _save_rag_content_locally(rag_doc) -> Optional[str]:
        """将 RAG 文档内容保存到本地（用于反向同步）"""
        from base.plugins.document.services.document_service import _get_storage_dir

        content = getattr(rag_doc, "content", "") or ""
        if not content:
            return None

        storage_dir = _get_storage_dir()
        timestamp = int(time.time())
        file_name = f"{timestamp}_{rag_doc.file_name or 'rag_doc.txt'}"
        local_path = storage_dir / file_name

        with open(str(local_path), "w", encoding="utf-8") as f:
            f.write(content)

        return str(local_path)
