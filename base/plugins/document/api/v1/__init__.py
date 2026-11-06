"""
文档管理 API v1 路由聚合
"""
from fastapi import APIRouter
from base.plugins.document.api.v1.category_router import category_router
from base.plugins.document.api.v1.document_router import document_router
from base.plugins.document.api.v1.version_router import version_router
from base.plugins.document.api.v1.preview_router import preview_router
from base.plugins.document.api.v1.rag_router import rag_router

# 主路由器（符合插件管理器命名约定：__init___router）
__init___router = APIRouter()

__init___router.include_router(category_router, prefix="/categories", tags=["文档分类"])
__init___router.include_router(document_router, prefix="/documents", tags=["文档管理"])
__init___router.include_router(version_router, prefix="/versions", tags=["文档版本"])
__init___router.include_router(preview_router, prefix="/preview", tags=["文档预览"])
__init___router.include_router(rag_router, prefix="/rag", tags=["RAG 集成"])

# 兼容别名
router = __init___router

__all__ = ["__init___router", "router"]
