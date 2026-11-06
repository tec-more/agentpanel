"""
RAG (Retrieval-Augmented Generation) 模型
"""
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
from base.common.pgvector import VectorField


class RAGKnowledgeBase(BaseModel, TimestampMixin):
    """RAG知识库模型"""
    name = fields.CharField(max_length=200, description="知识库名称")
    description = fields.TextField(null=True, description="知识库描述")
    status = fields.CharField(max_length=20, default="active", description="状态: active/inactive")
    vector_dimension = fields.IntField(default=1024, description="向量维度")
    config = fields.JSONField(null=True, description="知识库配置")
    
    # 搜索模式配置: llm_index, pgvector
    search_mode = fields.CharField(max_length=20, default="pgvector", description="搜索模式: llm_index, pgvector")
    
    embedding_model = fields.ForeignKeyField(
        "models.LLMModel",
        related_name="rag_knowledge_bases",
        on_delete=fields.SET_NULL,
        null=True,
        description="关联的Embedding模型"
    )
    
    # 权限相关字段
    created_by = fields.ForeignKeyField(
        "models.User",
        related_name="rag_knowledge_bases_created",
        on_delete=fields.SET_NULL,
        null=True,
        description="创建者"
    )
    # 多对多关系：可见的部门
    visible_departments = fields.ManyToManyField(
        "models.Department",
        related_name="visible_rag_knowledge_bases",
        through="rag_knowledge_base_department",
        null=True,
        description="可见的部门列表"
    )
    is_public = fields.BooleanField(default=False, description="是否为公有文档库")
    # T1：access_level 收敛为 private/public；存量 dept 已迁移为 ResourceGrant（Q-A/Q3）
    access_level = fields.CharField(max_length=20, default="private", description="访问级别: private, public（dept 已废弃）")

    # ===== T1 多态归属扩展（溯源 02-§4.3 / Q-A / C-15）=====
    # owner_* 为归属唯一事实源；created_by 语义废弃，保留列只读
    owner_type = fields.CharField(max_length=3, default="usr", description="归属主体类型: cus/usr")
    owner_id = fields.BigIntField(null=True, description="归属主体 ID")

    class Meta:
        table = "rag_knowledge_base"
        # 索引策略溯源 §03-4：(owner_type, owner_id) 我的库 / (is_public) 公共库
        indexes = [
            ("owner_type", "owner_id"),
            ("is_public",),
        ]

    def __str__(self):
        return self.name


class RAGDocument(BaseModel, TimestampMixin):
    """RAG文档模型"""
    knowledge_base = fields.ForeignKeyField(
        "models.RAGKnowledgeBase",
        related_name="documents",
        on_delete=fields.CASCADE,
        description="所属知识库"
    )
    title = fields.CharField(max_length=500, description="文档标题")
    file_name = fields.CharField(max_length=500, null=True, description="文件名")
    file_type = fields.CharField(max_length=50, null=True, description="文件类型")
    file_size = fields.BigIntField(null=True, description="文件大小(字节)")
    file_path = fields.CharField(max_length=1000, null=True, description="文件存储路径")
    content = fields.TextField(null=True, description="文档内容")
    status = fields.CharField(max_length=20, default="pending", description="状态: pending/processing/completed/failed")
    chunk_count = fields.IntField(default=0, description="分块数量")
    metadata = fields.JSONField(null=True, description="元数据")
    
    # 审计字段
    created_by = fields.ForeignKeyField(
        "models.User",
        related_name="rag_documents_created",
        on_delete=fields.SET_NULL,
        null=True,
        description="创建者"
    )

    class Meta:
        table = "rag_document"

    def __str__(self):
        return self.title


class RAGDocumentChunk(BaseModel, TimestampMixin):
    """RAG文档片段模型（含向量）"""
    document = fields.ForeignKeyField(
        "models.RAGDocument",
        related_name="chunks",
        on_delete=fields.CASCADE,
        description="所属文档"
    )
    chunk_index = fields.IntField(description="分块索引")
    content = fields.TextField(description="分块内容")
    
    # VectorField: 使用 pgvector 格式存储向量
    vector = VectorField(dimension=1024, null=True, description="向量数据")
    
    metadata = fields.JSONField(null=True, description="元数据")
    node_id = fields.CharField(max_length=100, null=True, description="LlamaIndex Node ID")
    
    # 审计字段
    created_by = fields.ForeignKeyField(
        "models.User",
        related_name="rag_document_chunks_created",
        on_delete=fields.SET_NULL,
        null=True,
        description="创建者"
    )

    class Meta:
        table = "rag_document_chunk"

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
