"""
Embedding 服务工厂
"""
import logging
import asyncio
from typing import Optional, List
from base.plugins.llm.services.openai_service import OpenAIService
from base.plugins.llm.models.api_key import LLMApiKey
from base.plugins.llm.models.model import LLMModel
from llama_index.core.base.embeddings.base import BaseEmbedding

logger = logging.getLogger(__name__)


class CustomEmbedding(BaseEmbedding):
    """自定义通用 Embedding 类 - 支持任何 OpenAI 兼容接口"""
    
    # 定义私有字段
    _llm_service: object = None
    _model_name: str = ""
    
    def __init__(self, llm_service, model_name):
        super().__init__()
        object.__setattr__(self, '_llm_service', llm_service)
        object.__setattr__(self, '_model_name', model_name)
    
    def _get_text_embedding(self, text: str) -> List[float]:
        """同步获取文本 embedding"""
        # 使用线程池运行异步函数，避免事件循环冲突
        import threading
        
        result = [None]
        exc = [None]
        
        def worker():
            try:
                # 在线程中创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result[0] = loop.run_until_complete(self._aget_text_embedding(text))
            except Exception as e:
                exc[0] = e
        
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        
        if exc[0]:
            raise exc[0]
        return result[0]
    
    async def _aget_text_embedding(self, text: str) -> List[float]:
        """异步获取文本 embedding"""
        try:
            return await object.__getattribute__(self, '_llm_service').create_embedding(
                object.__getattribute__(self, '_model_name'), text)
        except Exception as e:
            logger.error(f"生成 embedding 失败: {e}")
            raise
    
    def _get_query_embedding(self, query: str) -> List[float]:
        """同步获取查询 embedding"""
        return self._get_text_embedding(query)
    
    async def _aget_query_embedding(self, query: str) -> List[float]:
        """异步获取查询 embedding"""
        return await self._aget_text_embedding(query)
    
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取 embeddings"""
        # 使用线程池运行异步函数，避免事件循环冲突
        import threading
        
        result = [None]
        exc = [None]
        
        def worker():
            try:
                # 在线程中创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result[0] = loop.run_until_complete(self._aget_text_embeddings(texts))
            except Exception as e:
                exc[0] = e
        
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        
        if exc[0]:
            raise exc[0]
        return result[0]
    
    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取 embeddings（异步）"""
        results = []
        for text in texts:
            result = await self._aget_text_embedding(text)
            results.append(result)
        return results


class EmbeddingFactory:
    """Embedding 工厂"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    async def get_embedding_model(model_id: int) -> BaseEmbedding:
        """获取 Embedding 模型 - 支持任意 OpenAI 兼容接口"""
        # 获取模型信息
        model = await LLMModel.get_or_none(id=model_id)
        if not model:
            raise ValueError(f"模型 {model_id} 不存在")
        
        # 获取 API Key
        api_key = await LLMApiKey.filter(model_id=model_id).first()
        if not api_key:
            raise ValueError(f"模型 {model_id} 没有可用的 API Key")
        
        # 创建 OpenAI 兼容的服务
        endpoint = api_key.endpoint_url or model.endpoint_url or "https://api.openai.com/v1"
        llm_service = OpenAIService(api_key.api_key, endpoint_url=endpoint)
        
        # 使用自定义的 Embedding 类，支持任意模型名
        logger.info(f"初始化 Embedding 模型: {model.model_id}, endpoint: {endpoint}")
        return CustomEmbedding(llm_service, model.model_id)
