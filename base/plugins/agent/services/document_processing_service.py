"""
文档处理服务
"""
from typing import List, Optional
import os
# 添加向量检索相关依赖
try:
    from langchain.document_loaders import PyPDFLoader, TextLoader, DocxLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.vectorstores import Chroma
    from langchain.docstore.document import Document
    VECTOR_SUPPORT = True
except ImportError:
    VECTOR_SUPPORT = False
    # 定义占位符，避免类型检查错误
    class Document:
        pass


class DocumentProcessingService:
    model = "document_processing"
    """文档处理服务"""
    
    @staticmethod
    def load_document(file_path: str) -> List['Document']:
        """加载文档"""
        if not VECTOR_SUPPORT:
            raise ValueError("向量支持未启用")
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            loader = PyPDFLoader(file_path)
        elif ext == '.txt':
            loader = TextLoader(file_path, encoding='utf-8')
        elif ext == '.docx':
            loader = DocxLoader(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")
        
        return loader.load()
    
    @staticmethod
    def split_document(documents: List['Document'], chunk_size: int = 1000, chunk_overlap: int = 100) -> List['Document']:
        """分割文档"""
        if not VECTOR_SUPPORT:
            raise ValueError("向量支持未启用")
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        return text_splitter.split_documents(documents)
    
    @staticmethod
    def create_vector_store(documents: List['Document'], persist_directory: str) -> 'Chroma':
        """创建向量存储"""
        if not VECTOR_SUPPORT:
            raise ValueError("向量支持未启用")
        
        embeddings = OpenAIEmbeddings()
        vector_store = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=persist_directory
        )
        vector_store.persist()
        return vector_store
    
    @staticmethod
    def process_document_directory(directory_path: str, persist_directory: str) -> 'Chroma':
        """处理目录中的所有文档"""
        if not VECTOR_SUPPORT:
            raise ValueError("向量支持未启用")
        
        all_documents = []
        
        # 遍历目录中的所有文件
        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # 加载文档
                    documents = DocumentProcessingService.load_document(file_path)
                    # 分割文档
                    split_docs = DocumentProcessingService.split_document(documents)
                    all_documents.extend(split_docs)
                    print(f"处理完成: {file_path}")
                except Exception as e:
                    print(f"处理失败: {file_path}, 错误: {e}")
        
        # 创建向量存储
        if all_documents:
            return DocumentProcessingService.create_vector_store(all_documents, persist_directory)
        else:
            raise ValueError("没有找到可处理的文档")
