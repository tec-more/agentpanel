"""
LlamaIndex 适配器服务
使用 Qdrant 作为向量存储
"""
import logging
from pathlib import Path
from typing import List, Optional
from llama_index.core import (
    Document,
    VectorStoreIndex,
    StorageContext,
    Settings
)
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core.base.embeddings.base import BaseEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from base.plugins.agent.models.rag import RAGKnowledgeBase, RAGDocument, RAGDocumentChunk

logger = logging.getLogger(__name__)


class LlamaIndexAdapter:
    """LlamaIndex 适配器"""
    
    def __init__(self, qdrant_host: str = None):
        """初始化 Qdrant 客户端 - 使用配置"""
        from base.common.setting import settings
        
        # 使用配置的 Qdrant 地址
        if qdrant_host:
            self.qdrant_host = qdrant_host
        else:
            self.qdrant_host = settings.QDRANT_HOST
        
        self.qdrant_client = None
        self._init_client()
    
    def _init_client(self):
        """初始化 Qdrant 客户端"""
        try:
            self.qdrant_client = QdrantClient(url=self.qdrant_host)
            logger.info(f"Qdrant 客户端初始化成功: {self.qdrant_host}")
        except Exception as e:
            logger.error(f"Qdrant 客户端初始化失败: {e}")
            raise
    
    def _get_collection_name(self, knowledge_base_id: int) -> str:
        """获取知识库对应的 Collection 名称"""
        return f"knowledge_base_{knowledge_base_id}"
    
    def _create_collection_if_not_exists(self, knowledge_base_id: int, vector_dim: int = 1024):
        """创建 Collection（如果不存在）"""
        collection_name = self._get_collection_name(knowledge_base_id)
        
        try:
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if collection_name not in collection_names:
                logger.info(f"创建 Collection: {collection_name}")
                self.qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_dim,
                        distance=Distance.COSINE
                    )
                )
        except Exception as e:
            logger.error(f"创建 Collection 失败: {e}")
            raise
    
    async def index_chunks(
        self,
        knowledge_base_id: int,
        chunks: List[RAGDocumentChunk],
        embed_model: BaseEmbedding
    ):
        """索引文档分片到 Qdrant"""
        collection_name = self._get_collection_name(knowledge_base_id)
        
        # 获取知识库配置
        kb = await RAGKnowledgeBase.get_or_none(id=knowledge_base_id)
        vector_dim = kb.vector_dimension if kb else 1024
        
        # 确保 Collection 存在
        self._create_collection_if_not_exists(knowledge_base_id, vector_dim)
        
        # 创建 LlamaIndex 文档
        documents = []
        for chunk in chunks:
            doc = Document(
                text=chunk.content,
                metadata={
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "knowledge_base_id": knowledge_base_id
                }
            )
            # 更新数据库的 node_id
            chunk.node_id = doc.id_
            await chunk.save()
            documents.append(doc)
        
        # 创建 VectorStore - 直接传递 qdrant_client
        vector_store = QdrantVectorStore(
            collection_name=collection_name,
            client=self.qdrant_client
        )
        
        # 创建索引
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        # 创建或加载索引
        try:
            index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=True
            )
            logger.info(f"成功索引 {len(documents)} 个分片到 Collection: {collection_name}")
            return index
        except Exception as e:
            logger.error(f"索引创建失败: {e}")
            raise
    
    async def search(
        self,
        knowledge_base_id: int,
        query_text: str,
        embed_model: BaseEmbedding,
        top_k: int = 5,
        similarity_threshold: Optional[float] = None
    ) -> List[dict]:
        """搜索向量搜索"""
        collection_name = self._get_collection_name(knowledge_base_id)
        
        # 检查 Collection 是否存在
        try:
            collections = self.qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if collection_name not in collection_names:
                raise ValueError(f"知识库 {knowledge_base_id} 的索引不存在，请先处理文档")
        except Exception as e:
            raise e
        
        # 加载索引
        vector_store = QdrantVectorStore(
            collection_name=collection_name,
            client=self.qdrant_client
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=embed_model
        )
        
        # 查询
        query_engine = index.as_query_engine(similarity_top_k=top_k)
        response = query_engine.query(query_text)
        
        # 处理结果
        results = []
        for node in response.source_nodes:
            chunk_id = node.metadata.get("chunk_id")
            similarity = node.score
            
            results.append({
                "chunk_id": chunk_id,
                "content": node.text,
                "similarity": similarity,
                "metadata": node.metadata
            })
        
        return results
    
    async def delete_collection(self, knowledge_base_id: int):
        """删除知识库的 Collection"""
        collection_name = self._get_collection_name(knowledge_base_id)
        try:
            self.qdrant_client.delete_collection(collection_name)
            logger.info(f"删除 Collection: {collection_name}")
        except Exception as e:
            logger.warning(f"删除 Collection 失败: {e}")
    
    async def delete_chunks_from_document(self, knowledge_base_id: int, chunk_ids: List[int]):
        """删除文档的分片索引"""
        collection_name = self._get_collection_name(knowledge_base_id)
        
        # 查找并删除
        # 这里可以通过 metadata 过滤
        # 为简化，这里先暂时跳过
        pass
