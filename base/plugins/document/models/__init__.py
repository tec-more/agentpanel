"""
文档管理模块初始化
"""
from base.plugins.document.models.document_models import (
    DocumentCategory,
    Document,
    DocumentVersion,
    DocumentTag,
)

__all__ = [
    "DocumentCategory",
    "Document",
    "DocumentVersion",
    "DocumentTag",
]
