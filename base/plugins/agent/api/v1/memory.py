"""
Memory API routes
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from base.plugins.agent.schemas.memory import MemoryCreate, MemoryUpdate, MemoryResponse
from base.plugins.agent.services.memory_service import MemoryService
from base.common.response import success_response, fail_response

memory_router = APIRouter(prefix="/memories", tags=["memories"])


@memory_router.post("/")
async def create_memory(memory: MemoryCreate):
    """Create a new memory"""
    try:
        created_memory = await MemoryService.create_memory(memory)
        data = MemoryResponse(
            id=created_memory.id,
            agent_id=created_memory.agent_id,
            content=created_memory.content,
            type=created_memory.type,
            importance=created_memory.importance,
            memory_mode=created_memory.memory_mode,
            customer_id=created_memory.customer_id,
            user_id=created_memory.user_id,
            created_at=created_memory.created_at,
            updated_at=created_memory.updated_at,
            recall_count=created_memory.recall_count,
            last_recalled_at=created_memory.last_recalled_at
        )
        return success_response(data=data.model_dump(), msg="记忆创建成功")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)
    except Exception as e:
        return fail_response(msg=str(e))


@memory_router.get("/")
async def get_memories(
    skip: int = 0,
    limit: int = 100,
    agent_id: int = None,
    memory_mode: str = None,
    customer_id: int = None,
    user_id: int = None,
    type: str = None
):
    """Get all memories"""
    from base.plugins.agent.models.memory import Memory
    from tortoise.expressions import Q
    
    # 构建查询条件
    query = Memory.all()
    
    if agent_id:
        query = query.filter(agent_id=agent_id)
    
    if memory_mode:
        query = query.filter(memory_mode=memory_mode)
    
    if type:
        query = query.filter(type=type)
    
    # 处理私有记忆的过滤
    if memory_mode == "private":
        if customer_id:
            query = query.filter(customer_id=customer_id)
        elif user_id:
            query = query.filter(user_id=user_id)
        else:
            query = query.filter(memory_mode="public")
    elif agent_id and not memory_mode:
        # 如果没有指定记忆模式，返回公共记忆加上该用户的私有记忆
        q_filter = Q(memory_mode="public")
        if customer_id:
            q_filter |= Q(memory_mode="private", customer_id=customer_id)
        elif user_id:
            q_filter |= Q(memory_mode="private", user_id=user_id)
        query = query.filter(q_filter)
    
    # 获取总数
    total = await query.count()
    
    # 获取分页数据
    memories = await query.offset(skip).limit(limit).order_by("-created_at").all()
    
    response = []
    for memory in memories:
        response.append(MemoryResponse(
            id=memory.id,
            agent_id=memory.agent_id,
            content=memory.content,
            type=memory.type,
            importance=memory.importance,
            memory_mode=memory.memory_mode,
            customer_id=memory.customer_id,
            user_id=memory.user_id,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            recall_count=memory.recall_count,
            last_recalled_at=memory.last_recalled_at
        ).model_dump())
    return success_response(data={"items": response, "total": total})


@memory_router.get("/{memory_id}")
async def get_memory(memory_id: int):
    """Get memory by ID"""
    memory = await MemoryService.get_memory_by_id(memory_id)
    if not memory:
        return fail_response(msg="记忆不存在", code=404)
    
    data = MemoryResponse(
        id=memory.id,
        agent_id=memory.agent_id,
        content=memory.content,
        type=memory.type,
        importance=memory.importance,
        memory_mode=memory.memory_mode,
        customer_id=memory.customer_id,
        user_id=memory.user_id,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        recall_count=memory.recall_count,
        last_recalled_at=memory.last_recalled_at
    )
    return success_response(data=data.model_dump())


@memory_router.put("/{memory_id}")
async def update_memory(memory_id: int, memory: MemoryUpdate):
    """Update memory"""
    updated_memory = await MemoryService.update_memory(memory_id, memory)
    if not updated_memory:
        return fail_response(msg="记忆不存在", code=404)
    
    data = MemoryResponse(
        id=updated_memory.id,
        agent_id=updated_memory.agent_id,
        content=updated_memory.content,
        type=updated_memory.type,
        importance=updated_memory.importance,
        memory_mode=updated_memory.memory_mode,
        customer_id=updated_memory.customer_id,
        user_id=updated_memory.user_id,
        created_at=updated_memory.created_at,
        updated_at=updated_memory.updated_at,
        recall_count=updated_memory.recall_count,
        last_recalled_at=updated_memory.last_recalled_at
    )
    return success_response(data=data.model_dump(), msg="记忆更新成功")


@memory_router.delete("/{memory_id}")
async def delete_memory(memory_id: int):
    """Delete memory"""
    success = await MemoryService.delete_memory(memory_id)
    if not success:
        return fail_response(msg="记忆不存在", code=404)
    return success_response(msg="记忆删除成功")


@memory_router.get("/agent/{agent_id}")
async def get_memories_by_agent(
    agent_id: int,
    memory_mode: str = None,
    customer_id: int = None,
    user_id: int = None
):
    """Get memories by agent"""
    memories = await MemoryService.get_memories_by_agent(
        agent_id,
        memory_mode=memory_mode,
        customer_id=customer_id,
        user_id=user_id
    )
    response = [MemoryResponse(
        id=m.id,
        agent_id=m.agent_id,
        content=m.content,
        type=m.type,
        importance=m.importance,
        memory_mode=m.memory_mode,
        customer_id=m.customer_id,
        user_id=m.user_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
        recall_count=m.recall_count,
        last_recalled_at=m.last_recalled_at
    ).model_dump() for m in memories]
    return success_response(data=response)


@memory_router.get("/agent/{agent_id}/type/{memory_type}")
async def get_memories_by_type(
    agent_id: int,
    memory_type: str,
    memory_mode: str = None,
    customer_id: int = None,
    user_id: int = None
):
    """Get memories by type"""
    memories = await MemoryService.get_memories_by_type(
        agent_id,
        memory_type,
        memory_mode=memory_mode,
        customer_id=customer_id,
        user_id=user_id
    )
    return success_response(data=memories)


@memory_router.post("/{memory_id}/recall")
async def recall_memory(memory_id: int):
    """Recall memory"""
    memory = await MemoryService.recall_memory(memory_id)
    if not memory:
        return fail_response(msg="记忆不存在", code=404)
    return success_response(data=memory)


@memory_router.get("/agent/{agent_id}/recent")
async def get_recent_memories(
    agent_id: int,
    limit: int = 10,
    customer_id: int = None,
    user_id: int = None
):
    """Get recent memories"""
    memories = await MemoryService.get_recent_memories(
        agent_id,
        limit,
        customer_id=customer_id,
        user_id=user_id
    )
    return success_response(data=memories)


@memory_router.get("/agent/{agent_id}/important")
async def get_important_memories(
    agent_id: int,
    limit: int = 10,
    customer_id: int = None,
    user_id: int = None
):
    """Get important memories"""
    memories = await MemoryService.get_important_memories(
        agent_id,
        limit,
        customer_id=customer_id,
        user_id=user_id
    )
    return success_response(data=memories)


@memory_router.get("/agent/{agent_id}/search")
async def search_memories(
    agent_id: int,
    query: str,
    customer_id: int = None,
    user_id: int = None
):
    """Search memories"""
    memories = await MemoryService.search_memories(
        agent_id,
        query,
        customer_id=customer_id,
        user_id=user_id
    )
    return success_response(data=memories)


@memory_router.get("/agent/{agent_id}/stats")
async def get_memory_stats(
    agent_id: int,
    customer_id: int = None,
    user_id: int = None
):
    """Get memory statistics"""
    stats = await MemoryService.get_memory_stats(
        agent_id,
        customer_id=customer_id,
        user_id=user_id
    )
    return success_response(data=stats)
