"""
RAG (Retrieval-Augmented Generation) API Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Query, UploadFile, File, Depends
from pydantic import BaseModel
from base.common.response import success_response, fail_response
from base.common.security import get_current_user_id
from base.common.permissions import (
    require_permission,
    require_any_permission,
    get_data_filter
)
from base.plugins.agent.schemas.rag import (
    RAGKnowledgeBaseCreate,
    RAGKnowledgeBaseUpdate,
    RAGKnowledgeBaseResponse,
    RAGDocumentCreate,
    RAGDocumentUpdate,
    RAGDocumentResponse,
    RAGDocumentChunkResponse,
    RAGSearchRequest,
    RAGSearchResponse
)
from base.plugins.agent.services.rag_service import RAGService

rag_router = APIRouter(prefix="/rag", tags=["rag"])


@rag_router.post("/knowledge-bases", response_model=RAGKnowledgeBaseResponse)
async def create_knowledge_base(
    data: RAGKnowledgeBaseCreate,
    user_id: int = require_permission("rag:kb:create")
):
    """创建知识库"""
    try:
        kb = await RAGService.create_knowledge_base(data, user_id=user_id)
        return success_response(data=RAGKnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            vector_dimension=kb.vector_dimension,
            config=kb.config,
            embedding_model_id=kb.embedding_model_id,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=0
        ), msg="知识库创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.get("/knowledge-bases")
async def list_knowledge_bases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    name: str = "",
    status: str = "",
    user_id: int = require_permission("rag:kb:list")
):
    """列出知识库（带数据权限过滤）"""
    try:
        data_filter = await get_data_filter(user_id, "dept_id")
        kbs = await RAGService.list_knowledge_bases_with_filter(data_filter, skip, limit, name, status)
        total = await RAGService.count_knowledge_bases_with_filter(data_filter, name, status)
        
        results = []
        for kb in kbs:
            doc_count = await RAGService.count_documents(kb.id)
            # 获取可见部门ID列表
            visible_dept_ids = []
            if hasattr(kb, 'visible_departments'):
                try:
                    depts = await kb.visible_departments.all()
                    visible_dept_ids = [d.id for d in depts]
                except:
                    pass
            results.append(RAGKnowledgeBaseResponse(
                id=kb.id,
                name=kb.name,
                description=kb.description,
                status=kb.status,
                vector_dimension=kb.vector_dimension,
                config=kb.config,
                embedding_model_id=kb.embedding_model_id,
                search_mode=kb.search_mode,
                is_public=kb.is_public if hasattr(kb, 'is_public') else False,
                access_level=kb.access_level if hasattr(kb, 'access_level') else 'private',
                created_by=kb.created_by_id if hasattr(kb, 'created_by_id') else None,
                dept_id=kb.dept_id if hasattr(kb, 'dept_id') else None,
                visible_department_ids=visible_dept_ids,
                created_at=kb.created_at,
                updated_at=kb.updated_at,
                document_count=doc_count
            ))
        
        return success_response(data={"items": results, "total": total})
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.get("/knowledge-bases/{kb_id}", response_model=RAGKnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: int,
    user_id: int = require_permission("rag:kb:view")
):
    """获取知识库详情"""
    try:
        kb = await RAGService.get_knowledge_base_with_permission(kb_id, user_id)
        if not kb:
            return fail_response(msg="知识库不存在或无权限", code=404)
        
        doc_count = await RAGService.count_documents(kb.id)
        # 获取可见部门ID列表
        visible_dept_ids = []
        if hasattr(kb, 'visible_departments'):
            try:
                depts = await kb.visible_departments.all()
                visible_dept_ids = [d.id for d in depts]
            except:
                pass
        return success_response(data=RAGKnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            vector_dimension=kb.vector_dimension,
            config=kb.config,
            embedding_model_id=kb.embedding_model_id,
            search_mode=kb.search_mode,
            is_public=kb.is_public if hasattr(kb, 'is_public') else False,
            access_level=kb.access_level if hasattr(kb, 'access_level') else 'private',
            created_by=kb.created_by_id if hasattr(kb, 'created_by_id') else None,
            dept_id=kb.dept_id if hasattr(kb, 'dept_id') else None,
            visible_department_ids=visible_dept_ids,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=doc_count
        ))
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.put("/knowledge-bases/{kb_id}", response_model=RAGKnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: int,
    data: RAGKnowledgeBaseUpdate,
    user_id: int = require_permission("rag:kb:update")
):
    """更新知识库"""
    try:
        kb = await RAGService.update_knowledge_base_with_permission(kb_id, data, user_id)
        if not kb:
            return fail_response(msg="知识库不存在或无权限", code=404)
        
        doc_count = await RAGService.count_documents(kb.id)
        # 获取可见部门ID列表
        visible_dept_ids = []
        if hasattr(kb, 'visible_departments'):
            try:
                depts = await kb.visible_departments.all()
                visible_dept_ids = [d.id for d in depts]
            except:
                pass
        return success_response(data=RAGKnowledgeBaseResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            vector_dimension=kb.vector_dimension,
            config=kb.config,
            embedding_model_id=kb.embedding_model_id,
            search_mode=kb.search_mode,
            is_public=kb.is_public if hasattr(kb, 'is_public') else False,
            access_level=kb.access_level if hasattr(kb, 'access_level') else 'private',
            created_by=kb.created_by_id if hasattr(kb, 'created_by_id') else None,
            dept_id=kb.dept_id if hasattr(kb, 'dept_id') else None,
            visible_department_ids=visible_dept_ids,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=doc_count
        ), msg="知识库更新成功")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.delete("/knowledge-bases/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    user_id: int = require_permission("rag:kb:delete")
):
    """删除知识库"""
    try:
        success = await RAGService.delete_knowledge_base_with_permission(kb_id, user_id)
        if not success:
            return fail_response(msg="知识库不存在或无权限", code=404)
        return success_response(msg="知识库删除成功")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.post("/documents", response_model=RAGDocumentResponse)
async def create_document(
    data: RAGDocumentCreate,
    user_id: int = require_permission("rag:doc:create")
):
    """创建文档"""
    try:
        # 验证知识库权限
        await RAGService.check_knowledge_base_permission(data.knowledge_base_id, user_id)
        doc = await RAGService.create_document(data, user_id)
        return success_response(data=RAGDocumentResponse(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            title=doc.title,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            file_path=doc.file_path,
            content=doc.content,
            metadata=doc.metadata,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ), msg="文档创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.get("/documents")
async def list_documents(
    knowledge_base_id: int = Query(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    title: str = "",
    status: str = "",
    user_id: int = require_permission("rag:doc:list")
):
    """列出文档"""
    try:
        await RAGService.check_knowledge_base_permission(knowledge_base_id, user_id)
        docs = await RAGService.list_documents(knowledge_base_id, skip, limit, title, status)
        total = await RAGService.count_documents(knowledge_base_id, title, status)
        
        results = []
        for doc in docs:
            results.append(RAGDocumentResponse(
                id=doc.id,
                knowledge_base_id=doc.knowledge_base_id,
                title=doc.title,
                file_name=doc.file_name,
                file_type=doc.file_type,
                file_size=doc.file_size,
                file_path=doc.file_path,
                content=doc.content,
                metadata=doc.metadata,
                status=doc.status,
                chunk_count=doc.chunk_count,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            ))
        
        return success_response(data={"items": results, "total": total})
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.get("/documents/{doc_id}", response_model=RAGDocumentResponse)
async def get_document(
    doc_id: int,
    user_id: int = require_permission("rag:doc:view")
):
    """获取文档详情"""
    try:
        doc = await RAGService.get_document_with_permission(doc_id, user_id)
        if not doc:
            return fail_response(msg="文档不存在或无权限", code=404)
        
        return success_response(data=RAGDocumentResponse(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            title=doc.title,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            file_path=doc.file_path,
            content=doc.content,
            metadata=doc.metadata,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ))
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.put("/documents/{doc_id}", response_model=RAGDocumentResponse)
async def update_document(
    doc_id: int,
    data: RAGDocumentUpdate,
    user_id: int = require_permission("rag:doc:update")
):
    """更新文档"""
    try:
        doc = await RAGService.update_document_with_permission(doc_id, data, user_id)
        if not doc:
            return fail_response(msg="文档不存在或无权限", code=404)
        
        return success_response(data=RAGDocumentResponse(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            title=doc.title,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            file_path=doc.file_path,
            content=doc.content,
            metadata=doc.metadata,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ), msg="文档更新成功")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    user_id: int = require_permission("rag:doc:delete")
):
    """删除文档"""
    try:
        success = await RAGService.delete_document_with_permission(doc_id, user_id)
        if not success:
            return fail_response(msg="文档不存在或无权限", code=404)
        return success_response(msg="文档删除成功")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.post("/documents/{doc_id}/process", response_model=RAGDocumentResponse)
async def process_document(
    doc_id: int, 
    chunk_size: int = 500, 
    chunk_overlap: int = 50,
    split_strategy: str = "smart",
    use_llama_index: bool = True,
    user_id: int = require_permission("rag:doc:process")
):
    """处理单个文档：分块并向量化"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"开始处理文档 ID={doc_id}, use_llama_index={use_llama_index}")
        
        # 验证文档权限
        await RAGService.check_document_permission(doc_id, user_id)
        
        if use_llama_index:
            from base.plugins.agent.services.rag_service import HybridRAGService
            logger.info("使用 HybridRAGService...")
            doc = await HybridRAGService.process_document_with_llama_index(doc_id, chunk_size, chunk_overlap, split_strategy, user_id)
        else:
            logger.info("使用 RAGService...")
            doc = await RAGService.process_document(doc_id, chunk_size, chunk_overlap, split_strategy, user_id)
        
        logger.info(f"文档处理成功 ID={doc.id}")
        
        return success_response(data=RAGDocumentResponse(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            title=doc.title,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            file_path=doc.file_path,
            content=doc.content,
            metadata=doc.metadata,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ), msg="文档处理成功")
    except Exception as e:
        logger.exception(f"文档处理失败: {str(e)}")
        return fail_response(msg=str(e))


class BatchProcessDocumentsRequest(BaseModel):
    """批量处理文档请求"""
    doc_ids: List[int]
    chunk_size: int = 500
    chunk_overlap: int = 50
    split_strategy: str = "smart"
    use_llama_index: bool = True


@rag_router.post("/documents/batch-process")
async def batch_process_documents(
    request: BatchProcessDocumentsRequest,
    user_id: int = require_permission("rag:doc:process")
):
    """批量处理文档：分块并向量化"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        doc_ids = request.doc_ids
        if not doc_ids:
            return fail_response(msg="请至少选择一个文档")
        
        logger.info(f"开始批量处理文档，共 {len(doc_ids)} 个")
        
        results = []
        errors = []
        
        for doc_id in doc_ids:
            try:
                # 验证每个文档的权限
                await RAGService.check_document_permission(doc_id, user_id)
                
                if request.use_llama_index:
                    from base.plugins.agent.services.rag_service import HybridRAGService
                    doc = await HybridRAGService.process_document_with_llama_index(
                        doc_id, 
                        request.chunk_size, 
                        request.chunk_overlap, 
                        request.split_strategy,
                        user_id
                    )
                else:
                    doc = await RAGService.process_document(
                        doc_id, 
                        request.chunk_size, 
                        request.chunk_overlap, 
                        request.split_strategy,
                        user_id
                    )
                
                results.append({
                    "doc_id": doc.id,
                    "title": doc.title,
                    "status": "success",
                    "chunk_count": doc.chunk_count
                })
                logger.info(f"文档处理成功 ID={doc.id}")
            except Exception as e:
                errors.append({
                    "doc_id": doc_id,
                    "error": str(e)
                })
                logger.error(f"文档处理失败 ID={doc_id}, error: {str(e)}")
        
        return success_response(data={
            "total": len(doc_ids),
            "success": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors
        }, msg=f"批量处理完成：成功 {len(results)} 个，失败 {len(errors)} 个")
    except Exception as e:
        logger.exception(f"批量处理失败: {str(e)}")
        return fail_response(msg=str(e))


@rag_router.get("/documents/{doc_id}/chunks")
async def list_chunks(
    doc_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: int = require_permission("rag:chunk:view")
):
    """列出文档片段"""
    try:
        await RAGService.check_document_permission(doc_id, user_id)
        chunks = await RAGService.list_chunks(doc_id, skip, limit)
        results = []
        for chunk in chunks:
            results.append(RAGDocumentChunkResponse(
                id=chunk.id,
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata=chunk.metadata,
                created_at=chunk.created_at,
                updated_at=chunk.updated_at
            ))
        return success_response(data={"items": results, "total": len(results)})
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.delete("/chunks/{chunk_id}")
async def delete_chunk(
    chunk_id: int,
    user_id: int = require_permission("rag:chunk:delete")
):
    """删除文档片段"""
    try:
        success = await RAGService.delete_chunk_with_permission(chunk_id, user_id)
        if not success:
            return fail_response(msg="片段不存在或无权限", code=404)
        return success_response(msg="片段删除成功")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.post("/search")
async def search(
    request: RAGSearchRequest,
    use_llama_index: Optional[bool] = None,
    user_id: int = require_permission("rag:search")
):
    """向量搜索（支持跨知识库搜索，简化版）"""
    try:
        # 判断是单个知识库搜索还是跨知识库搜索
        if request.knowledge_base_ids and len(request.knowledge_base_ids) > 0:
            # 验证所有知识库的权限
            for kb_id in request.knowledge_base_ids:
                await RAGService.check_knowledge_base_permission(kb_id, user_id)
            
            # 跨知识库搜索
            results = await RAGService.search_across_knowledge_bases(
                request.knowledge_base_ids,
                request.query,
                request.top_k,
                request.similarity_threshold
            )
            
            chunk_responses = []
            for result in results:
                chunk = result['chunk']
                chunk_responses.append(RAGDocumentChunkResponse(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    metadata=chunk.metadata,
                    created_at=chunk.created_at,
                    updated_at=chunk.updated_at,
                    similarity=result['similarity'],
                    knowledge_base_id=result.get('knowledge_base_id'),
                    knowledge_base_name=result.get('knowledge_base_name')
                ))
            
            return success_response(data=RAGSearchResponse(
                query=request.query,
                results=chunk_responses,
                total=len(chunk_responses)
            ))
        
        elif request.knowledge_base_id:
            # 验证知识库权限
            await RAGService.check_knowledge_base_permission(request.knowledge_base_id, user_id)
            
            # 单个知识库搜索
            # 获取知识库配置
            kb = await RAGService.get_knowledge_base(request.knowledge_base_id)
            if not kb:
                return fail_response(msg="知识库不存在")
            
            # 根据知识库配置决定使用哪种模式
            search_mode = kb.search_mode or "pgvector"
            
            use_llama_index_mode = False
            
            if search_mode == "llm_index":
                use_llama_index_mode = True
            
            # 如果传入了参数优先使用参数
            if use_llama_index is not None:
                use_llama_index_mode = use_llama_index
            
            if use_llama_index_mode:
                from base.plugins.agent.services.rag_service import HybridRAGService
                # 使用 LlamaIndex 搜索
                results = await HybridRAGService.search_with_llama_index(
                    request.knowledge_base_id,
                    request.query,
                    request.top_k,
                    request.similarity_threshold
                )
                
                chunk_responses = []
                for result in results:
                    # 获取数据库里的完整信息
                    chunk = await RAGService.get_chunk(result.get('chunk_id'))
                    if chunk:
                        chunk_responses.append(RAGDocumentChunkResponse(
                            id=chunk.id,
                            document_id=chunk.document_id,
                            chunk_index=chunk.chunk_index,
                            content=chunk.content,
                            metadata=chunk.metadata,
                            created_at=chunk.created_at,
                            updated_at=chunk.updated_at,
                            similarity=result.get('similarity'),
                            knowledge_base_id=request.knowledge_base_id,
                            knowledge_base_name=kb.name
                        ))
            else:
                # 使用 pgvector 搜索
                results = await RAGService.search(
                    request.knowledge_base_id,
                    request.query,
                    request.top_k,
                    request.similarity_threshold
                )
                
                chunk_responses = []
                for result in results:
                    chunk = result['chunk']
                    chunk_responses.append(RAGDocumentChunkResponse(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        metadata=chunk.metadata,
                        created_at=chunk.created_at,
                        updated_at=chunk.updated_at,
                        similarity=result['similarity'],
                        knowledge_base_id=result.get('knowledge_base_id'),
                        knowledge_base_name=result.get('knowledge_base_name')
                    ))
            
            return success_response(data=RAGSearchResponse(
                query=request.query,
                results=chunk_responses,
                total=len(chunk_responses)
            ))
        else:
            return fail_response(msg="请指定 knowledge_base_id 或 knowledge_base_ids")
    except Exception as e:
        return fail_response(msg=str(e))


@rag_router.post("/documents/upload")
async def upload_document(
    knowledge_base_id: int = Query(...),
    file: UploadFile = File(...),
    user_id: int = require_permission("rag:doc:create")
):
    """上传文档并提取内容"""
    try:
        await RAGService.check_knowledge_base_permission(knowledge_base_id, user_id)
        doc = await RAGService.upload_document(knowledge_base_id, file, user_id)
        return success_response(data=RAGDocumentResponse(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            title=doc.title,
            file_name=doc.file_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            file_path=doc.file_path,
            content=doc.content,
            metadata=doc.metadata,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        ), msg="文档上传成功")
    except Exception as e:
        return fail_response(msg=str(e))
