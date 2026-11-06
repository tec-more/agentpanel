"""
文档管理 Service 模块初始化
"""
from base.plugins.document.services.document_service import (
    CategoryService,
    DocumentService,
    VersionService,
    PreviewService,
)
from base.plugins.document.services.rag_integration_service import (
    RAGIntegrationService,
    RAG_BUSINESS_TYPE,
)

__all__ = [
    "CategoryService",
    "DocumentService",
    "VersionService",
    "PreviewService",
    "RAGIntegrationService",
    "RAG_BUSINESS_TYPE",
]
