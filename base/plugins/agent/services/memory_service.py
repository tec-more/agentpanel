"""
Memory service
"""
from typing import List, Optional, Dict, Any
from tortoise.exceptions import DoesNotExist
from datetime import datetime
from base.plugins.agent.models.memory import Memory
from base.plugins.agent.models.agent import Agent
from base.plugins.agent.schemas.memory import MemoryCreate, MemoryUpdate

# 添加向量检索相关依赖
try:
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.vectorstores import Chroma
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.docstore.document import Document
    VECTOR_SUPPORT = True
except ImportError:
    VECTOR_SUPPORT = False

# 向量存储目录
VECTOR_STORE_DIR = "./vector_stores"

import logging
logger = logging.getLogger(__name__)

class MemoryService:
    model = "memory"
    """Memory service class"""

    @staticmethod
    async def create_memory(memory_data: MemoryCreate) -> Memory:
        """Create memory"""
        # Check if agent exists
        try:
            agent = await Agent.get(id=memory_data.agent_id)
        except DoesNotExist:
            raise ValueError("Agent not found")
        
        # Check memory capacity - 对于私有记忆，只检查该用户的记忆数量
        if memory_data.memory_mode == "private":
            if memory_data.customer_id:
                memory_count = await Memory.filter(
                    agent_id=memory_data.agent_id,
                    memory_mode="private",
                    customer_id=memory_data.customer_id
                ).count()
            elif memory_data.user_id:
                memory_count = await Memory.filter(
                    agent_id=memory_data.agent_id,
                    memory_mode="private",
                    user_id=memory_data.user_id
                ).count()
            else:
                memory_count = 0
        else:
            memory_count = await Memory.filter(
                agent_id=memory_data.agent_id,
                memory_mode="public"
            ).count()
        
        if memory_count >= agent.memory_capacity:
            # Remove oldest memories if capacity exceeded
            if memory_data.memory_mode == "private":
                if memory_data.customer_id:
                    oldest_memories = await Memory.filter(
                        agent_id=memory_data.agent_id,
                        memory_mode="private",
                        customer_id=memory_data.customer_id
                    ).order_by("created_at").limit(memory_count - agent.memory_capacity + 1)
                elif memory_data.user_id:
                    oldest_memories = await Memory.filter(
                        agent_id=memory_data.agent_id,
                        memory_mode="private",
                        user_id=memory_data.user_id
                    ).order_by("created_at").limit(memory_count - agent.memory_capacity + 1)
                else:
                    oldest_memories = []
            else:
                oldest_memories = await Memory.filter(
                    agent_id=memory_data.agent_id,
                    memory_mode="public"
                ).order_by("created_at").limit(memory_count - agent.memory_capacity + 1)
            
            for old_memory in oldest_memories:
                await old_memory.delete()
        
        memory = await Memory.create(
            agent_id=memory_data.agent_id,
            content=memory_data.content,
            type=memory_data.type,
            importance=memory_data.importance,
            memory_mode=memory_data.memory_mode,
            customer_id=memory_data.customer_id,
            user_id=memory_data.user_id
        )
        
        # 将记忆添加到向量存储
        await MemoryService.add_memory_to_vector_store(memory_data.agent_id, memory)
        
        return memory

    @staticmethod
    async def get_memories(skip: int = 0, limit: int = 100) -> List[Memory]:
        """Get memory list"""
        memories = await Memory.all().offset(skip).limit(limit).prefetch_related('agent')
        return memories

    @staticmethod
    async def get_memory_by_id(memory_id: int) -> Optional[Memory]:
        """Get memory by ID"""
        try:
            memory = await Memory.get(id=memory_id).prefetch_related('agent')
            return memory
        except DoesNotExist:
            return None

    @staticmethod
    async def update_memory(memory_id: int, memory_data: MemoryUpdate) -> Optional[Memory]:
        """Update memory"""
        memory = await MemoryService.get_memory_by_id(memory_id)
        if not memory:
            return None

        update_data = memory_data.model_dump(exclude_unset=True)
        await memory.update_from_dict(update_data)
        await memory.save()
        
        # 更新向量存储中的记忆
        await MemoryService.update_memory_in_vector_store(memory.agent_id, memory)
        
        return memory

    @staticmethod
    async def delete_memory(memory_id: int) -> bool:
        """Delete memory"""
        memory = await MemoryService.get_memory_by_id(memory_id)
        if not memory:
            return False

        await memory.delete()
        return True

    @staticmethod
    async def get_memories_by_agent(
        agent_id: int,
        memory_mode: Optional[str] = None,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> List[Memory]:
        """Get memories by agent with optional filters"""
        query = Memory.filter(agent_id=agent_id)
        
        if memory_mode:
            query = query.filter(memory_mode=memory_mode)
        
        # 如果是私有记忆模式，需要过滤用户
        if memory_mode == "private":
            if customer_id:
                query = query.filter(customer_id=customer_id)
            elif user_id:
                query = query.filter(user_id=user_id)
            # 如果私有记忆但没有用户ID，则只返回公共记忆
            else:
                query = query.filter(memory_mode="public")
        # 如果是公共记忆或没有指定模式，则返回公共记忆加上该用户的私有记忆
        else:
            from tortoise.expressions import Q
            q_filter = Q(memory_mode="public")
            if customer_id:
                q_filter |= Q(memory_mode="private", customer_id=customer_id)
            elif user_id:
                q_filter |= Q(memory_mode="private", user_id=user_id)
            query = query.filter(q_filter)
        
        memories = await query.order_by("-created_at").all()
        return memories

    @staticmethod
    async def get_memories_by_type(
        agent_id: int,
        memory_type: str,
        memory_mode: Optional[str] = None,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> List[Memory]:
        """Get memories by type with optional filters"""
        query = Memory.filter(agent_id=agent_id, type=memory_type)
        
        if memory_mode:
            query = query.filter(memory_mode=memory_mode)
        
        # 如果是私有记忆模式，需要过滤用户
        if memory_mode == "private":
            if customer_id:
                query = query.filter(customer_id=customer_id)
            elif user_id:
                query = query.filter(user_id=user_id)
            # 如果私有记忆但没有用户ID，则只返回公共记忆
            else:
                query = query.filter(memory_mode="public")
        # 如果是公共记忆或没有指定模式，则返回公共记忆加上该用户的私有记忆
        else:
            from tortoise.expressions import Q
            q_filter = Q(memory_mode="public")
            if customer_id:
                q_filter |= Q(memory_mode="private", customer_id=customer_id)
            elif user_id:
                q_filter |= Q(memory_mode="private", user_id=user_id)
            query = query.filter(q_filter)
        
        memories = await query.order_by("-created_at").all()
        return memories

    @staticmethod
    async def recall_memory(memory_id: int) -> Optional[Memory]:
        """Recall memory (increment recall count and update last recalled time)"""
        memory = await MemoryService.get_memory_by_id(memory_id)
        if not memory:
            return None
        
        memory.recall_count += 1
        memory.last_recalled_at = datetime.utcnow()
        await memory.save()
        return memory

    @staticmethod
    async def get_recent_memories(
        agent_id: int,
        limit: int = 10,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> List[Memory]:
        """Get recent memories with user filtering - 使用原始SQL查询"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"获取最近记忆，agent_id={agent_id} (使用原始SQL)")
        
        try:
            from tortoise import Tortoise
            conn = Tortoise.get_connection("postgres")
            logger.info(f"数据库连接状态: 已连接")
            
            # 构建 SQL 查询
            if customer_id:
                sql = """
                    SELECT * FROM memory 
                    WHERE agent_id = $1 AND (memory_mode = 'public' OR (memory_mode = 'private' AND customer_id = $2))
                    ORDER BY created_at DESC 
                    LIMIT $3
                """
                params = [agent_id, customer_id, limit]
            elif user_id:
                sql = """
                    SELECT * FROM memory 
                    WHERE agent_id = $1 AND (memory_mode = 'public' OR (memory_mode = 'private' AND user_id = $2))
                    ORDER BY created_at DESC 
                    LIMIT $3
                """
                params = [agent_id, user_id, limit]
            else:
                sql = """
                    SELECT * FROM memory 
                    WHERE agent_id = $1 AND memory_mode = 'public'
                    ORDER BY created_at DESC 
                    LIMIT $2
                """
                params = [agent_id, limit]
            
            logger.info(f"执行原始SQL查询")
            # 执行原始 SQL 查询
            results = await conn.execute_query_dict(sql, params)
            
            logger.info(f"原始SQL查询完成，获取到条记录")
            
            # 转换为 Memory 对象
            memories = []
            for row in results:
                memory = Memory(
                    id=row.get('id'),
                    agent_id=row.get('agent_id'),
                    content=row.get('content'),
                    type=row.get('type'),
                    importance=row.get('importance'),
                    recall_count=row.get('recall_count', 0),
                    memory_mode=row.get('memory_mode', 'public'),
                    customer_id=row.get('customer_id'),
                    user_id=row.get('user_id'),
                    created_at=row.get('created_at'),
                    updated_at=row.get('updated_at'),
                    last_recalled_at=row.get('last_recalled_at')
                )
                memories.append(memory)
            
            logger.info(f"成功转换 {len(memories)} 条记忆")
            return memories
            
        except Exception as e:
            logger.error(f"原始SQL查询失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return []

    @staticmethod
    async def get_important_memories(
        agent_id: int,
        limit: int = 10,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> List[Memory]:
        """Get important memories with user filtering - 使用原始SQL查询"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"获取重要记忆，agent_id={agent_id} (使用原始SQL)")
        
        try:
            from tortoise import Tortoise
            conn = Tortoise.get_connection("postgres")
            
            # 构建 SQL 查询
            if customer_id:
                sql = """
                    SELECT * FROM memory 
                    WHERE agent_id = $1 AND (memory_mode = 'public' OR (memory_mode = 'private' AND customer_id = $2))
                    ORDER BY importance DESC, created_at DESC 
                    LIMIT $3
                """
                params = [agent_id, customer_id, limit]
            elif user_id:
                sql = """
                    SELECT * FROM memory 
                    WHERE agent_id = $1 AND (memory_mode = 'public' OR (memory_mode = 'private' AND user_id = $2))
                    ORDER BY importance DESC, created_at DESC 
                    LIMIT $3
                """
                params = [agent_id, user_id, limit]
            else:
                sql = """
                    SELECT * FROM memory 
                    WHERE agent_id = $1 AND memory_mode = 'public'
                    ORDER BY importance DESC, created_at DESC 
                    LIMIT $2
                """
                params = [agent_id, limit]
            
            logger.info(f"执行原始SQL查询")
            # 执行原始 SQL 查询
            results = await conn.execute_query_dict(sql, params)
            
            logger.info(f"原始SQL查询完成，获取 条记录")
            
            # 转换为 Memory 对象
            memories = []
            for row in results:
                memory = Memory(
                    id=row.get('id'),
                    agent_id=row.get('agent_id'),
                    content=row.get('content'),
                    type=row.get('type'),
                    importance=row.get('importance'),
                    recall_count=row.get('recall_count', 0),
                    memory_mode=row.get('memory_mode', 'public'),
                    customer_id=row.get('customer_id'),
                    user_id=row.get('user_id'),
                    created_at=row.get('created_at'),
                    updated_at=row.get('updated_at'),
                    last_recalled_at=row.get('last_recalled_at')
                )
                memories.append(memory)
            
            logger.info(f"成功转换 {len(memories)} 条重要记忆")
            return memories
            
        except Exception as e:
            logger.error(f"原始SQL查询失败: {e}")
            import traceback
            logger.error(f"异常堆栈: {traceback.format_exc()}")
            return []

    @staticmethod
    async def search_memories(
        agent_id: int,
        query: str,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> List[Memory]:
        """Search memories by content with user filtering"""
        from tortoise.expressions import Q
        q_filter = Q(memory_mode="public")
        if customer_id:
            q_filter |= Q(memory_mode="private", customer_id=customer_id)
        elif user_id:
            q_filter |= Q(memory_mode="private", user_id=user_id)
        
        memories = await Memory.filter(agent_id=agent_id).filter(q_filter).all()
        filtered_memories = [
            memory for memory in memories 
            if query.lower() in memory.content.lower()
        ]
        return filtered_memories

    @staticmethod
    async def get_memory_stats(
        agent_id: int,
        customer_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> dict:
        """Get memory statistics with user filtering"""
        from tortoise.expressions import Q
        
        # 统计公共记忆
        total_public = await Memory.filter(agent_id=agent_id, memory_mode="public").count()
        short_term_public = await Memory.filter(agent_id=agent_id, memory_mode="public", type="short_term").count()
        long_term_public = await Memory.filter(agent_id=agent_id, memory_mode="public", type="long_term").count()
        
        # 统计私有记忆
        total_private = 0
        short_term_private = 0
        long_term_private = 0
        
        if customer_id:
            total_private = await Memory.filter(agent_id=agent_id, memory_mode="private", customer_id=customer_id).count()
            short_term_private = await Memory.filter(agent_id=agent_id, memory_mode="private", customer_id=customer_id, type="short_term").count()
            long_term_private = await Memory.filter(agent_id=agent_id, memory_mode="private", customer_id=customer_id, type="long_term").count()
        elif user_id:
            total_private = await Memory.filter(agent_id=agent_id, memory_mode="private", user_id=user_id).count()
            short_term_private = await Memory.filter(agent_id=agent_id, memory_mode="private", user_id=user_id, type="short_term").count()
            long_term_private = await Memory.filter(agent_id=agent_id, memory_mode="private", user_id=user_id, type="long_term").count()
        
        return {
            "total_public": total_public,
            "total_private": total_private,
            "total_memories": total_public + total_private,
            "short_term_public": short_term_public,
            "long_term_public": long_term_public,
            "short_term_private": short_term_private,
            "long_term_private": long_term_private,
            "memory_capacity": (await Agent.get(id=agent_id)).memory_capacity
        }

    @staticmethod
    def get_vector_store(agent_id: int):
        """获取智能体的向量存储"""
        if not VECTOR_SUPPORT:
            return None
        
        try:
            embeddings = OpenAIEmbeddings()
            vector_store = Chroma(
                persist_directory=f"{VECTOR_STORE_DIR}/agent_{agent_id}",
                embedding_function=embeddings
            )
            return vector_store
        except Exception as e:
            print(f"Error getting vector store: {e}")
            return None

    @staticmethod
    async def add_memory_to_vector_store(agent_id: int, memory: Memory):
        """将记忆添加到向量存储"""
        if not VECTOR_SUPPORT:
            return False
        
        try:
            vector_store = MemoryService.get_vector_store(agent_id)
            if not vector_store:
                return False
            
            # 创建文档对象
            document = Document(
                page_content=memory.content,
                metadata={
                    "memory_id": memory.id,
                    "agent_id": agent_id,
                    "type": memory.type,
                    "importance": memory.importance,
                    "created_at": memory.created_at.isoformat()
                }
            )
            
            # 添加到向量存储
            vector_store.add_documents([document])
            vector_store.persist()
            return True
        except Exception as e:
            print(f"Error adding memory to vector store: {e}")
            return False

    @staticmethod
    async def retrieve_relevant_memories(agent_id: int, query: str, k: int = 5) -> List[Memory]:
        """根据查询检索相关记忆"""
        if not VECTOR_SUPPORT:
            # 如果不支持向量检索，使用传统搜索
            return await MemoryService.search_memories(agent_id, query)
        
        try:
            vector_store = MemoryService.get_vector_store(agent_id)
            if not vector_store:
                return await MemoryService.search_memories(agent_id, query)
            
            # 向量检索
            results = vector_store.similarity_search(query, k=k)
            
            # 获取记忆对象
            memory_ids = [int(doc.metadata.get("memory_id")) for doc in results if doc.metadata.get("memory_id")]
            if not memory_ids:
                return []
            
            memories = await Memory.filter(id__in=memory_ids).all()
            return memories
        except Exception as e:
            print(f"Error retrieving relevant memories: {e}")
            return await MemoryService.search_memories(agent_id, query)

    @staticmethod
    async def update_memory_in_vector_store(agent_id: int, memory: Memory):
        """更新向量存储中的记忆"""
        if not VECTOR_SUPPORT:
            return False
        
        try:
            # 先删除旧记忆
            vector_store = MemoryService.get_vector_store(agent_id)
            if not vector_store:
                return False
            
            # 删除旧记忆
            vector_store.delete([str(memory.id)])
            
            # 添加更新后的记忆
            return await MemoryService.add_memory_to_vector_store(agent_id, memory)
        except Exception as e:
            print(f"Error updating memory in vector store: {e}")
            return False

    @staticmethod
    async def clear_vector_store(agent_id: int):
        """清空智能体的向量存储"""
        if not VECTOR_SUPPORT:
            return False
        
        try:
            vector_store = MemoryService.get_vector_store(agent_id)
            if not vector_store:
                return False
            
            vector_store.delete([])  # 清空所有向量
            vector_store.persist()
            return True
        except Exception as e:
            print(f"Error clearing vector store: {e}")
            return False