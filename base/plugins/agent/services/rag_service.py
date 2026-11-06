"""
RAG (Retrieval-Augmented Generation) Service
"""
import logging
import re
import os
from pathlib import Path
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from base.plugins.agent.models.rag import (
    RAGKnowledgeBase,
    RAGDocument,
    RAGDocumentChunk
)
from base.plugins.agent.schemas.rag import (
    RAGKnowledgeBaseCreate,
    RAGKnowledgeBaseUpdate,
    RAGDocumentCreate,
    RAGDocumentUpdate,
    RAGDocumentChunkCreate
)
from base.common.permissions import get_user_data_scope_cached, get_user_permissions_cached
from base.common.security import get_current_user
logger = logging.getLogger(__name__)


class TextSplitter:
    """文本切片器"""
    
    @staticmethod
    def split_by_paragraph(text: str) -> List[str]:
        """按段落分割"""
        paragraphs = re.split(r'\n\s*\n', text.strip())
        return [p.strip() for p in paragraphs if p.strip()]
    
    @staticmethod
    def split_by_sentence(text: str) -> List[str]:
        """按句子分割"""
        sentence_endings = r'[.!?。！？]'
        sentences = re.split(f'({sentence_endings})', text)
        result = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1])
            else:
                result.append(sentences[i])
        return [s.strip() for s in result if s.strip()]


class VectorService:
    model = "vector"
    """向量服务（已简化，只保留 pgvector 支持）"""

    VECTOR_DIMENSION = 1024


class RAGService:
    model = "rag"
    """RAG服务"""

    @staticmethod
    async def create_knowledge_base(data: RAGKnowledgeBaseCreate) -> RAGKnowledgeBase:
        """创建知识库"""
        kb = await RAGKnowledgeBase.create(
            name=data.name,
            description=data.description,
            status=data.status,
            vector_dimension=data.vector_dimension,
            config=data.config,
            embedding_model_id=data.embedding_model_id
        )
        logger.info(f"创建知识库: {kb.name} (ID: {kb.id})")
        return kb

    @staticmethod
    async def get_knowledge_base(kb_id: int) -> Optional[RAGKnowledgeBase]:
        """获取知识库"""
        return await RAGKnowledgeBase.get_or_none(id=kb_id)

    @staticmethod
    async def list_knowledge_bases(skip: int = 0, limit: int = 100, name: str = "", status: str = "") -> List[RAGKnowledgeBase]:
        """列出知识库"""
        query = RAGKnowledgeBase.all()
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        return await query.offset(skip).limit(limit).order_by("-created_at")

    @staticmethod
    async def count_knowledge_bases(name: str = "", status: str = "") -> int:
        """统计知识库数量"""
        query = RAGKnowledgeBase.all()
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        return await query.count()

    @staticmethod
    async def update_knowledge_base(kb_id: int, data: RAGKnowledgeBaseUpdate) -> Optional[RAGKnowledgeBase]:
        """更新知识库"""
        kb = await RAGService.get_knowledge_base(kb_id)
        if not kb:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(kb, field, value)
        await kb.save()
        logger.info(f"更新知识库: {kb.name} (ID: {kb.id})")
        return kb

    @staticmethod
    async def delete_knowledge_base(kb_id: int) -> bool:
        """删除知识库"""
        kb = await RAGService.get_knowledge_base(kb_id)
        if not kb:
            return False
        await kb.delete()
        logger.info(f"删除知识库: {kb.name} (ID: {kb.id})")
        return True

    @staticmethod
    async def create_document(
        data: RAGDocumentCreate, 
        user_id: Optional[int] = None
    ) -> RAGDocument:
        """创建文档"""
        doc = await RAGDocument.create(
            knowledge_base_id=data.knowledge_base_id,
            title=data.title,
            file_name=data.file_name,
            file_type=data.file_type,
            file_size=data.file_size,
            file_path=data.file_path,
            content=data.content,
            metadata=data.metadata,
            created_by_id=user_id
        )
        logger.info(f"创建文档: {doc.title} (ID: {doc.id}, 创建者: {user_id})")
        return doc

    @staticmethod
    async def get_document(doc_id: int) -> Optional[RAGDocument]:
        """获取文档"""
        return await RAGDocument.get_or_none(id=doc_id)

    @staticmethod
    async def list_documents(kb_id: int, skip: int = 0, limit: int = 100, title: str = "", status: str = "") -> List[RAGDocument]:
        """列出文档"""
        query = RAGDocument.filter(knowledge_base_id=kb_id)
        if title:
            query = query.filter(title__icontains=title)
        if status:
            query = query.filter(status=status)
        return await query.offset(skip).limit(limit).order_by("-created_at")

    @staticmethod
    async def count_documents(kb_id: int, title: str = "", status: str = "") -> int:
        """统计文档数量"""
        query = RAGDocument.filter(knowledge_base_id=kb_id)
        if title:
            query = query.filter(title__icontains=title)
        if status:
            query = query.filter(status=status)
        return await query.count()

    @staticmethod
    async def update_document(doc_id: int, data: RAGDocumentUpdate) -> Optional[RAGDocument]:
        """更新文档"""
        doc = await RAGService.get_document(doc_id)
        if not doc:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(doc, field, value)
        await doc.save()
        logger.info(f"更新文档: {doc.title} (ID: {doc.id})")
        return doc

    @staticmethod
    async def delete_document(doc_id: int) -> bool:
        """删除文档"""
        doc = await RAGService.get_document(doc_id)
        if not doc:
            return False
        await doc.delete()
        logger.info(f"删除文档: {doc.title} (ID: {doc.id})")
        return True

    @staticmethod
    async def create_chunk(
        data: RAGDocumentChunkCreate, 
        vector: Optional[List[float]] = None,
        user_id: Optional[int] = None
    ) -> RAGDocumentChunk:
        """创建文档片段（简化，只使用 pgvector）"""
        chunk = await RAGDocumentChunk.create(
            document_id=data.document_id,
            chunk_index=data.chunk_index,
            content=data.content,
            vector=vector,
            metadata=data.metadata,
            created_by_id=user_id
        )
        logger.info(f"创建文档片段: {chunk.id} (文档ID: {chunk.document_id}, 创建者: {user_id})")
        return chunk

    @staticmethod
    async def get_chunk(chunk_id: int) -> Optional[RAGDocumentChunk]:
        """获取文档片段"""
        return await RAGDocumentChunk.get_or_none(id=chunk_id)

    @staticmethod
    async def list_chunks(doc_id: int, skip: int = 0, limit: int = 100) -> List[RAGDocumentChunk]:
        """列出文档片段"""
        return await RAGDocumentChunk.filter(document_id=doc_id).offset(skip).limit(limit).order_by("chunk_index")

    @staticmethod
    async def delete_chunk(chunk_id: int) -> bool:
        """删除文档片段"""
        chunk = await RAGService.get_chunk(chunk_id)
        if not chunk:
            return False
        await chunk.delete()
        logger.info(f"删除文档片段: {chunk.id}")
        return True

    @staticmethod
    async def _get_embedding_service(knowledge_base: RAGKnowledgeBase):
        """获取Embedding服务"""
        # 获取知识库关联的模型
        if not knowledge_base.embedding_model:
            raise ValueError("请先为知识库配置Embedding模型")
        
        model = await knowledge_base.embedding_model
        
        # 获取该模型的API密钥
        from base.plugins.llm.models.api_key import LLMApiKey
        api_key = await LLMApiKey.filter(model_id=model.id, status="active").first()
        
        if not api_key:
            raise ValueError("未找到该模型的可用API密钥")
        
        # 获取厂商
        provider = await model.provider
        
        # 初始化OpenAI服务
        endpoint = api_key.endpoint_url or model.endpoint_url or "https://api.openai.com/v1"
        from base.plugins.llm.services.localai_service import LocalAIService
        return LocalAIService(api_key=api_key.api_key, endpoint_url=endpoint), model.model_id

    @staticmethod
    async def process_document(
        doc_id: int, 
        chunk_size: int = 500, 
        chunk_overlap: int = 50,
        split_strategy: str = "smart",
        user_id: Optional[int] = None
    ) -> RAGDocument:
        """处理文档：分块并向量化（简化，只使用 pgvector）"""
        doc = await RAGService.get_document(doc_id)
        if not doc:
            raise ValueError("文档不存在")

        if not doc.content:
            raise ValueError("文档内容为空")

        # 获取知识库
        knowledge_base = await doc.knowledge_base
        
        # 获取Embedding服务
        embedding_service, model_id = await RAGService._get_embedding_service(knowledge_base)

        doc.status = "processing"
        await doc.save()

        try:
            content = doc.content
            
            if split_strategy == "smart":
                chunks = RAGService._smart_split_text(content, chunk_size, chunk_overlap)
            elif split_strategy == "paragraph":
                chunks = RAGService._split_by_paragraph(content, chunk_size, chunk_overlap)
            else:
                chunks = RAGService._simple_split_text(content, chunk_size, chunk_overlap)

            await RAGDocumentChunk.filter(document_id=doc_id).delete()

            # 创建片段并向量化
            for idx, chunk_content in enumerate(chunks):
                try:
                    # 生成向量
                    vector = await embedding_service.create_embedding(model_id, chunk_content)
                    
                    await RAGService.create_chunk(
                        RAGDocumentChunkCreate(
                            document_id=doc_id,
                            chunk_index=idx,
                            content=chunk_content
                        ),
                        vector=vector,
                        user_id=user_id
                    )
                    logger.info(f"片段 {idx} 向量化完成")
                except Exception as e:
                    logger.error(f"片段 {idx} 向量化失败: {str(e)}")
                    # 即使向量化失败，也保存片段（不带向量）
                    await RAGService.create_chunk(
                        RAGDocumentChunkCreate(
                            document_id=doc_id,
                            chunk_index=idx,
                            content=chunk_content
                        ),
                        user_id=user_id
                    )

            doc.chunk_count = len(chunks)
            doc.status = "completed"
            await doc.save()
            logger.info(f"文档处理完成: {doc.title} (ID: {doc.id}), 分块数: {len(chunks)}")
            return doc
        except Exception as e:
            doc.status = "failed"
            await doc.save()
            logger.error(f"文档处理失败: {doc.title} (ID: {doc.id}), 错误: {str(e)}")
            raise

    @staticmethod
    def _simple_split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """简单的文本分块方法"""
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + chunk_size, text_length)

            if end < text_length:
                last_space = text.rfind(' ', start, end)
                last_newline = text.rfind('\n', start, end)
                if last_space > start:
                    end = last_space
                elif last_newline > start:
                    end = last_newline

            chunks.append(text[start:end])
            start = end - chunk_overlap

            if start < 0:
                start = 0

        return chunks

    @staticmethod
    def _smart_split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """智能文本分块：优先按段落，然后句子，最后字符"""
        chunks = []
        
        paragraphs = TextSplitter.split_by_paragraph(text)
        
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= chunk_size:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                
                if len(paragraph) > chunk_size:
                    sentences = TextSplitter.split_by_sentence(paragraph)
                    current_chunk = ""
                    
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) <= chunk_size:
                            if current_chunk:
                                current_chunk += " "
                            current_chunk += sentence
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            
                            if len(sentence) > chunk_size:
                                sub_chunks = RAGService._simple_split_text(sentence, chunk_size, chunk_overlap)
                                chunks.extend(sub_chunks)
                                current_chunk = ""
                            else:
                                current_chunk = sentence
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = ""
                else:
                    current_chunk = paragraph
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    @staticmethod
    def _split_by_paragraph(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """按段落分块"""
        paragraphs = TextSplitter.split_by_paragraph(text)
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= chunk_size:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    @staticmethod
    async def search(
        knowledge_base_id: int,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None
    ) -> List[dict]:
        """向量搜索（简化，只使用 pgvector）"""
        kb = await RAGService.get_knowledge_base(knowledge_base_id)
        if not kb:
            raise ValueError("知识库不存在")

        # 获取Embedding服务并生成查询向量
        embedding_service, model_id = await RAGService._get_embedding_service(kb)
        query_vector = await embedding_service.create_embedding(model_id, query_text)

        # 使用 pgvector 搜索
        return await RAGService._search_with_pgvector(
            knowledge_base_id,
            query_vector,
            top_k,
            similarity_threshold
        )
    
    @staticmethod
    async def search_across_knowledge_bases(
        knowledge_base_ids: List[int],
        query_text: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None
    ) -> List[dict]:
        """跨知识库向量搜索"""
        if not knowledge_base_ids:
            raise ValueError("至少需要指定一个知识库 ID")
        
        all_results = []
        
        # 分组处理：相同 embedding model 的知识库可以一起处理（优化）
        kb_groups = {}
        for kb_id in knowledge_base_ids:
            kb = await RAGService.get_knowledge_base(kb_id)
            if not kb or kb.status != "active":
                continue
            
            # 按 embedding model 分组
            model_id = kb.embedding_model_id
            if model_id not in kb_groups:
                kb_groups[model_id] = {
                    "kb": kb,
                    "ids": [kb_id]
                }
            else:
                kb_groups[model_id]["ids"].append(kb_id)
        
        # 处理每一组知识库
        for group in kb_groups.values():
            kb = group["kb"]
            kb_ids = group["ids"]
            
            try:
                # 获取 embedding 服务
                embedding_service, model_id = await RAGService._get_embedding_service(kb)
                query_vector = await embedding_service.create_embedding(model_id, query_text)
                
                # 根据搜索模式处理
                search_mode = kb.search_mode or "pgvector"
                
                if search_mode == "llm_index":
                    # 使用 LlamaIndex 搜索
                    from base.plugins.agent.services.rag_service import HybridRAGService
                    for kb_id in kb_ids:
                        try:
                            results = await HybridRAGService.search_with_llama_index(
                                kb_id,
                                query_text,
                                top_k,
                                similarity_threshold
                            )
                            # 添加知识库信息
                            for res in results:
                                chunk = await RAGService.get_chunk(res.get('chunk_id'))
                                if chunk:
                                    all_results.append({
                                        'chunk': chunk,
                                        'similarity': res.get('similarity'),
                                        'knowledge_base_id': kb_id,
                                        'knowledge_base_name': kb.name
                                    })
                        except Exception as e:
                            logger.error(f"知识库 {kb_id} 使用 LlamaIndex 搜索失败: {e}")
                

                
                else:
                    # pgvector（默认） - 支持一次查询多个知识库
                    try:
                        results = await RAGService._search_with_pgvector_across_kbs(
                            kb_ids,
                            query_vector,
                            top_k * len(kb_ids),
                            similarity_threshold
                        )
                        for res in results:
                            all_results.append(res)
                    except Exception as e:
                        logger.error(f"跨知识库 pgvector 搜索失败: {e}")
                        # 回退到逐个搜索
                        for kb_id in kb_ids:
                            try:
                                results = await RAGService._search_with_pgvector(
                                    kb_id,
                                    query_vector,
                                    top_k,
                                    similarity_threshold
                                )
                                for res in results:
                                    res['knowledge_base_id'] = kb_id
                                    res['knowledge_base_name'] = kb.name
                                    all_results.append(res)
                            except Exception as e2:
                                logger.error(f"知识库 {kb_id} pgvector 搜索失败: {e2}")
            
            except Exception as e:
                logger.error(f"处理知识库组失败: {e}")
        
        # 合并并排序所有结果
        all_results.sort(key=lambda x: x['similarity'], reverse=True)
        return all_results[:top_k]

    @staticmethod
    async def _search_with_pgvector(
        knowledge_base_id: int,
        query_vector: List[float],
        top_k: int = 5,
        similarity_threshold: Optional[float] = None
    ) -> List[dict]:
        """使用 pgvector 的向量搜索"""
        from tortoise import Tortoise

        # 构建 pgvector 格式的查询向量
        vector_str = "[" + ",".join([f"{v:.10f}" for v in query_vector]) + "]"
        
        # 使用原始 SQL 进行查询
        conn = Tortoise.get_connection("postgres")
        
        # 构建查询
        sql_query = f"""
        SELECT 
            c.id,
            c.document_id,
            c.chunk_index,
            c.content,
            c.metadata,
            c.created_at,
            c.updated_at,
            d.knowledge_base_id,
            kb.name as knowledge_base_name,
            (c.vector <=> '{vector_str}') as distance
        FROM rag_document_chunk c
        JOIN rag_document d ON c.document_id = d.id
        JOIN rag_knowledge_base kb ON d.knowledge_base_id = kb.id
        WHERE d.knowledge_base_id = $1
            AND c.vector IS NOT NULL
        ORDER BY distance
        LIMIT $2
        """
        
        results = []
        try:
            # 执行查询
            raw_results = await conn.execute_query_dict(
                sql_query,
                [knowledge_base_id, top_k]
            )
            
            # 转换结果
            for row in raw_results:
                # 距离转换为相似度
                # pgvector 的余弦距离范围是 0 到 2，我们需要转换为相似度
                distance = row.get('distance', 2.0)
                similarity = 1.0 - (distance / 2.0)
                
                if similarity_threshold and similarity < similarity_threshold:
                    continue
                
                # 获取完整的 ORM 对象
                chunk = await RAGDocumentChunk.get_or_none(id=row['id'])
                
                if chunk:
                    results.append({
                        'chunk': chunk,
                        'similarity': similarity,
                        'knowledge_base_id': row.get('knowledge_base_id'),
                        'knowledge_base_name': row.get('knowledge_base_name')
                    })
            
            # 按相似度排序（可能已有，但确保正确
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
        except Exception as e:
            logger.error(f"pgvector 搜索出错: {e}")
            raise
        
        return results[:top_k]
    
    @staticmethod
    async def _search_with_pgvector_across_kbs(
        knowledge_base_ids: List[int],
        query_vector: List[float],
        top_k: int = 10,
        similarity_threshold: Optional[float] = None
    ) -> List[dict]:
        """使用 pgvector 的跨知识库向量搜索"""
        from tortoise import Tortoise

        if not knowledge_base_ids:
            return []
        
        # 构建 pgvector 格式的查询向量
        vector_str = "[" + ",".join([f"{v:.10f}" for v in query_vector]) + "]"
        
        # 使用原始 SQL 进行查询
        conn = Tortoise.get_connection("postgres")
        
        # 构建 IN 查询占位符
        placeholders = ','.join(['$' + str(i+2) for i in range(len(knowledge_base_ids))])
        
        # 构建查询
        sql_query = f"""
        SELECT 
            c.id,
            c.document_id,
            c.chunk_index,
            c.content,
            c.metadata,
            c.created_at,
            c.updated_at,
            d.knowledge_base_id,
            kb.name as knowledge_base_name,
            (c.vector <=> '{vector_str}') as distance
        FROM rag_document_chunk c
        JOIN rag_document d ON c.document_id = d.id
        JOIN rag_knowledge_base kb ON d.knowledge_base_id = kb.id
        WHERE d.knowledge_base_id IN ({placeholders})
            AND c.vector IS NOT NULL
        ORDER BY distance
        LIMIT $1
        """
        
        results = []
        try:
            # 执行查询
            params = [top_k] + knowledge_base_ids
            raw_results = await conn.execute_query_dict(sql_query, params)
            
            # 转换结果
            for row in raw_results:
                # 距离转换为相似度
                distance = row.get('distance', 2.0)
                similarity = 1.0 - (distance / 2.0)
                
                if similarity_threshold and similarity < similarity_threshold:
                    continue
                
                # 获取完整的 ORM 对象
                chunk = await RAGDocumentChunk.get_or_none(id=row['id'])
                
                if chunk:
                    results.append({
                        'chunk': chunk,
                        'similarity': similarity,
                        'knowledge_base_id': row.get('knowledge_base_id'),
                        'knowledge_base_name': row.get('knowledge_base_name')
                    })
            
            # 按相似度排序
            results.sort(key=lambda x: x['similarity'], reverse=True)
            
        except Exception as e:
            logger.error(f"跨知识库 pgvector 搜索出错: {e}")
            raise
        
        return results[:top_k]

    @staticmethod
    async def update_chunk_vector(
        chunk_id: int, 
        vector: List[float]
    ) -> Optional[RAGDocumentChunk]:
        """更新片段向量（简化，只使用 pgvector）"""
        chunk = await RAGService.get_chunk(chunk_id)
        if not chunk:
            return None

        # 只更新 pgvector 格式
        chunk.vector = vector
        await chunk.save()
        return chunk

    @staticmethod
    async def upload_document(
        knowledge_base_id: int,
        file: UploadFile,
        user_id: Optional[int] = None
    ) -> RAGDocument:
        """上传文档"""
        return await DocumentProcessor.upload_document(knowledge_base_id, file, user_id)


class DocumentProcessor:
    """文档内容提取器"""
    
    @staticmethod
    async def extract_text(file: UploadFile) -> tuple[str, str, int]:
        """从上传的文件中提取文本内容（使用新的解析器）"""
        from base.plugins.agent.services.document_parser import DocumentParser
        
        # 重置文件指针（因为可能读取了多次）
        await file.seek(0)
        
        # 使用新的解析器
        content, file_type = await DocumentParser.parse_file(file)
        
        # 重新获取文件大小
        await file.seek(0)
        file_content = await file.read()
        file_size = len(file_content)
        
        return content, file_type, file_size
    
    @staticmethod
    async def upload_document(
        knowledge_base_id: int,
        file: UploadFile,
        user_id: Optional[int] = None
    ) -> RAGDocument:
        """上传文档并创建记录"""
        filename = file.filename or "unknown"
        title = Path(filename).stem
        
        try:
            content, file_type, file_size = await DocumentProcessor.extract_text(file)
            
            doc = await RAGDocument.create(
                knowledge_base_id=knowledge_base_id,
                title=title,
                file_name=filename,
                file_type=file_type,
                file_size=file_size,
                content=content,
                status="pending",
                metadata={
                    "uploaded": True,
                    "file_type": file_type
                },
                created_by_id=user_id
            )
            
            logger.info(f"文档上传成功: {filename} (ID: {doc.id}, 创建者: {user_id})")
            return doc
            
        except Exception as e:
            logger.error(f"文档上传失败: {filename} - {str(e)}")
            raise


class HybridRAGService:
    model = "hybrid_r_a_g"
    """混合 RAG 服务"""
    
    # 切换方式：可以通过配置或环境变量切换
    USE_LLAMA_INDEX = True  # 默认使用 LlamaIndex
    
    @staticmethod
    async def process_document_with_llama_index(
        doc_id: int,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        split_strategy: str = "smart",
        user_id: Optional[int] = None
    ):
        """使用 LlamaIndex 处理文档"""
        from base.plugins.agent.services.llama_index_adapter import LlamaIndexAdapter
        from base.plugins.agent.services.embedding_factory import EmbeddingFactory
        
        # 获取文档
        doc = await RAGService.get_document(doc_id)
        if not doc:
            raise ValueError("文档不存在")
        
        # 获取知识库
        knowledge_base = await doc.knowledge_base
        if not knowledge_base.embedding_model:
            raise ValueError("请先为知识库配置 Embedding 模型")
        
        # 获取 Embedding 模型
        embedding_model_id = knowledge_base.embedding_model_id
        embed_model = await EmbeddingFactory.get_embedding_model(embedding_model_id)
        
        # 先调用原有处理创建分片（用于保存数据）
        # 这样数据库里还有数据，只是用 LlamaIndex 来做向量存储
        await RAGService.process_document(doc_id, chunk_size, chunk_overlap, split_strategy, user_id)
        
        # 现在再用 LlamaIndex 索引
        chunks = await RAGService.list_chunks(doc_id)
        
        adapter = LlamaIndexAdapter()
        await adapter.index_chunks(knowledge_base.id, chunks, embed_model)
        
        return doc
    
    @staticmethod
    async def search_with_llama_index(
        knowledge_base_id: int,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None
    ):
        """使用 LlamaIndex 搜索"""
        from base.plugins.agent.services.llama_index_adapter import LlamaIndexAdapter
        from base.plugins.agent.services.embedding_factory import EmbeddingFactory
        
        kb = await RAGService.get_knowledge_base(knowledge_base_id)
        if not kb:
            raise ValueError("知识库不存在")
        
        if not kb.embedding_model:
            raise ValueError("请先为知识库配置 Embedding 模型")
        
        # 获取 Embedding 模型
        embedding_model_id = kb.embedding_model_id
        embed_model = await EmbeddingFactory.get_embedding_model(embedding_model_id)
        
        adapter = LlamaIndexAdapter()
        return await adapter.search(
            knowledge_base_id,
            query_text,
            embed_model,
            top_k,
            similarity_threshold
        )


class RAGPermissionService:
    model = "rag_permission"
    """RAG 权限服务"""

    @staticmethod
    async def get_user_info(user_id: int):
        """获取用户信息"""
        from base.core.users.models.users import User
        return await User.get_or_none(id=user_id)

    @staticmethod
    async def check_public_or_permission(
        knowledge_base: RAGKnowledgeBase, 
        user_id: int
    ) -> bool:
        """检查知识库是否公开或用户有权访问"""
        # 检查是否公开 - 兼容字段可能不存在的情况
        try:
            if (hasattr(knowledge_base, 'access_level') and knowledge_base.access_level == "public") or \
               (hasattr(knowledge_base, 'is_public') and knowledge_base.is_public):
                return True
        except:
            pass
        
        # 检查部门权限 - 支持多部门
        try:
            if hasattr(knowledge_base, 'access_level') and knowledge_base.access_level == "dept":
                user = await RAGPermissionService.get_user_info(user_id)
                if user and hasattr(knowledge_base, 'visible_departments'):
                    # 检查用户部门是否在可见部门列表中
                    if user.dept_id:
                        depts = await knowledge_base.visible_departments.filter(id=user.dept_id).count()
                        if depts > 0:
                            return True
                    # 如果没有设置可见部门，检查是否有旧的dept_id字段（向后兼容）
                    if hasattr(knowledge_base, 'dept_id') and knowledge_base.dept_id and user.dept_id == knowledge_base.dept_id:
                        return True
        except Exception as e:
            pass
        
        # 检查创建者权限
        try:
            if hasattr(knowledge_base, 'created_by_id') and knowledge_base.created_by_id == user_id:
                return True
        except:
            pass
        
        # 如果权限字段不存在，默认允许访问（向后兼容）
        if not hasattr(knowledge_base, 'is_public') and not hasattr(knowledge_base, 'access_level'):
            return True
        
        return False

    @staticmethod
    async def check_knowledge_base_permission(
        knowledge_base_id: int, 
        user_id: int
    ) -> bool:
        """检查用户是否有权访问知识库"""
        kb = await RAGService.get_knowledge_base(knowledge_base_id)
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")

        has_access = await RAGPermissionService.check_public_or_permission(kb, user_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="无权限访问该知识库")

        return True

    @staticmethod
    async def check_document_permission(
        document_id: int,
        user_id: int
    ) -> bool:
        """检查用户是否有权访问文档"""
        doc = await RAGService.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        kb = await doc.knowledge_base
        return await RAGPermissionService.check_knowledge_base_permission(kb.id, user_id)

    @staticmethod
    async def get_accessible_knowledge_bases_query(
        user_id: int,
        data_filter: Optional[dict] = None
    ):
        """获取用户可访问的知识库查询"""
        from base.common.permissions import get_user_data_scope_cached
        data_scope = await get_user_data_scope_cached(user_id)

        if data_scope == "all":
            query = RAGKnowledgeBase.all()
        elif data_scope == "dept":
            user = await RAGPermissionService.get_user_info(user_id)
            if user and user.dept_id:
                query = RAGKnowledgeBase.filter(
                    (RAGKnowledgeBase.dept_id == user.dept_id) | 
                    (RAGKnowledgeBase.access_level == "public") | 
                    (RAGKnowledgeBase.is_public == True)
                )
            else:
                query = RAGKnowledgeBase.filter(
                    (RAGKnowledgeBase.access_level == "public") | 
                    (RAGKnowledgeBase.is_public == True)
                )
        else:
            query = RAGKnowledgeBase.filter(
                (RAGKnowledgeBase.created_by_id == user_id) | 
                (RAGKnowledgeBase.access_level == "public") | 
                (RAGKnowledgeBase.is_public == True)
            )

        if data_filter and "dept" in data_filter:
            query = query.filter(dept_id__in=data_filter["dept"])

        return query


async def add_permission_methods_to_rag_service():
    """为RAGService添加权限相关方法"""

    @staticmethod
    async def create_knowledge_base_with_permission(
        data: RAGKnowledgeBaseCreate,
        user_id: int
    ) -> RAGKnowledgeBase:
        """创建知识库（带创建者信息）"""
        kb = await RAGKnowledgeBase.create(
            name=data.name,
            description=data.description,
            status=data.status,
            vector_dimension=data.vector_dimension,
            config=data.config,
            embedding_model_id=data.embedding_model_id,
            is_public=data.is_public,
            access_level=data.access_level,
            created_by_id=user_id
        )
        
        # 如果指定了可见部门，建立关联
        if data.visible_department_ids:
            from base.core.dept.models.department import Department
            for dept_id in data.visible_department_ids:
                dept = await Department.get_or_none(id=dept_id)
                if dept:
                    await kb.visible_departments.add(dept)
        
        logger.info(f"创建知识库: {kb.name} (ID: {kb.id}, 创建者: {user_id})")
        return kb

    @staticmethod
    async def list_knowledge_bases_with_filter(
        data_filter: Optional[dict],
        skip: int = 0,
        limit: int = 100,
        name: str = "",
        status: str = ""
    ) -> List[RAGKnowledgeBase]:
        """列出知识库（带权限过滤）"""
        user_id = data_filter.get("user_id") if data_filter else None
        if not user_id:
            query = RAGKnowledgeBase.all()
        else:
            query = await RAGPermissionService.get_accessible_knowledge_bases_query(
                user_id, data_filter
            )

        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        return await query.offset(skip).limit(limit).order_by("-created_at")

    @staticmethod
    async def count_knowledge_bases_with_filter(
        data_filter: Optional[dict],
        name: str = "",
        status: str = ""
    ) -> int:
        """统计知识库数量（带权限过滤）"""
        user_id = data_filter.get("user_id") if data_filter else None
        if not user_id:
            query = RAGKnowledgeBase.all()
        else:
            query = await RAGPermissionService.get_accessible_knowledge_bases_query(
                user_id, data_filter
            )

        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        return await query.count()

    @staticmethod
    async def get_knowledge_base_with_permission(
        kb_id: int,
        user_id: int
    ) -> Optional[RAGKnowledgeBase]:
        """获取知识库（带权限检查）"""
        kb = await RAGService.get_knowledge_base(kb_id)
        if not kb:
            return None

        has_access = await RAGPermissionService.check_public_or_permission(kb, user_id)
        if not has_access:
            return None

        return kb

    @staticmethod
    async def update_knowledge_base_with_permission(
        kb_id: int,
        data: RAGKnowledgeBaseUpdate,
        user_id: int
    ) -> Optional[RAGKnowledgeBase]:
        """更新知识库（带权限检查）"""
        kb = await RAGService.get_knowledge_base_with_permission(kb_id, user_id)
        if not kb:
            return None

        # 更新普通字段
        update_data = data.model_dump(exclude_unset=True, exclude={"visible_department_ids"})
        for field, value in update_data.items():
            setattr(kb, field, value)
        await kb.save()
        
        # 更新部门关联
        if hasattr(data, "visible_department_ids") and data.visible_department_ids is not None:
            from base.core.dept.models.department import Department
            # 先清空现有关联
            await kb.visible_departments.clear()
            # 添加新的关联
            for dept_id in data.visible_department_ids:
                dept = await Department.get_or_none(id=dept_id)
                if dept:
                    await kb.visible_departments.add(dept)
        
        logger.info(f"更新知识库: {kb.name} (ID: {kb.id})")
        return kb

    @staticmethod
    async def delete_knowledge_base_with_permission(
        kb_id: int,
        user_id: int
    ) -> bool:
        """删除知识库（带权限检查）"""
        kb = await RAGService.get_knowledge_base_with_permission(kb_id, user_id)
        if not kb:
            return False

        await kb.delete()
        logger.info(f"删除知识库: {kb.name} (ID: {kb.id})")
        return True

    @staticmethod
    async def get_document_with_permission(
        doc_id: int,
        user_id: int
    ) -> Optional[RAGDocument]:
        """获取文档（带权限检查）"""
        doc = await RAGService.get_document(doc_id)
        if not doc:
            return None

        await RAGPermissionService.check_document_permission(doc_id, user_id)
        return doc

    @staticmethod
    async def update_document_with_permission(
        doc_id: int,
        data: RAGDocumentUpdate,
        user_id: int
    ) -> Optional[RAGDocument]:
        """更新文档（带权限检查）"""
        await RAGPermissionService.check_document_permission(doc_id, user_id)
        return await RAGService.update_document(doc_id, data)

    @staticmethod
    async def delete_document_with_permission(
        doc_id: int,
        user_id: int
    ) -> bool:
        """删除文档（带权限检查）"""
        await RAGPermissionService.check_document_permission(doc_id, user_id)
        return await RAGService.delete_document(doc_id)

    @staticmethod
    async def delete_chunk_with_permission(
        chunk_id: int,
        user_id: int
    ) -> bool:
        """删除文档片段（带权限检查）"""
        chunk = await RAGService.get_chunk(chunk_id)
        if not chunk:
            return False

        doc = await chunk.document
        await RAGPermissionService.check_document_permission(doc.id, user_id)
        return await RAGService.delete_chunk(chunk_id)

    RAGService.create_knowledge_base_with_permission = create_knowledge_base_with_permission
    RAGService.list_knowledge_bases_with_filter = list_knowledge_bases_with_filter
    RAGService.count_knowledge_bases_with_filter = count_knowledge_bases_with_filter
    RAGService.get_knowledge_base_with_permission = get_knowledge_base_with_permission
    RAGService.update_knowledge_base_with_permission = update_knowledge_base_with_permission
    RAGService.delete_knowledge_base_with_permission = delete_knowledge_base_with_permission
    RAGService.check_knowledge_base_permission = RAGPermissionService.check_knowledge_base_permission
    RAGService.check_document_permission = RAGPermissionService.check_document_permission
    RAGService.get_document_with_permission = get_document_with_permission
    RAGService.update_document_with_permission = update_document_with_permission
    RAGService.delete_document_with_permission = delete_document_with_permission
    RAGService.delete_chunk_with_permission = delete_chunk_with_permission

    logger.info("已为RAGService添加权限方法")


import asyncio
asyncio.create_task(add_permission_methods_to_rag_service())

