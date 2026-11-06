"""
Agent API routes
"""
from typing import List, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from base.plugins.agent.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from base.plugins.agent.services.agent_service import AgentService
from base.plugins.agent.services.checkpoint_service import CheckpointService
from base.common.security import get_current_actor
from base.common.response import success_response, fail_response
import uuid
import asyncio
import logging
logger = logging.getLogger(__name__)
# 执行管理器 - 跟踪所有执行的任务
execution_manager = {
    # execution_id: {
    #     'task': asyncio.Task,
    #     'agent_id': int,
    #     'is_cancelled': bool
    # }
}

agent_router = APIRouter(prefix="/agents", tags=["agents"])
execution_router = APIRouter(prefix="/executions", tags=["executions"])


@agent_router.post("/")
async def create_agent(agent: AgentCreate):
    """Create a new agent"""
    try:
        created_agent = await AgentService.create_agent(agent)
        
        skill_count = 0
        memory_count = 0
        workflow_count = 0
        dialog_flow_count = 0
        
        data = AgentResponse(
            id=created_agent.id,
            name=created_agent.name,
            description=created_agent.description,
            status=created_agent.status,
            memory_capacity=created_agent.memory_capacity,
            llm_model_id=None,
            created_at=created_agent.created_at,
            updated_at=created_agent.updated_at,
            skill_count=skill_count,
            memory_count=memory_count,
            workflow_count=workflow_count,
            dialog_flow_count=dialog_flow_count
        )
        
        return success_response(data=data, msg="智能体创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@agent_router.post("/import")
async def import_agent(import_data: dict):
    """Import agent from template"""
    try:
        imported_agent = await AgentService.import_agent(import_data)
        
        skill_count = 0
        memory_count = 0
        workflow_count = 0
        dialog_flow_count = 0
        
        data = {
            "id": imported_agent.id,
            "name": imported_agent.name,
            "description": imported_agent.description,
            "status": imported_agent.status,
            "memory_capacity": imported_agent.memory_capacity,
            "created_at": imported_agent.created_at.isoformat() if imported_agent.created_at else None,
            "updated_at": imported_agent.updated_at.isoformat() if imported_agent.updated_at else None,
            "skill_count": skill_count,
            "memory_count": memory_count
        }
        
        return success_response(data=data, msg="智能体导入成功")
    except Exception as e:
        import traceback
        return fail_response(msg=f"导入失败: {str(e)}", data={"traceback": traceback.format_exc()})


@agent_router.get("/")
async def get_agents(skip: int = 0, limit: int = 100, name: str = "", status: str = ""):
    """Get all agents"""
    from base.plugins.agent.models.agent import Agent
    
    # 构建查询条件
    query = Agent.all()
    
    if name:
        query = query.filter(name__icontains=name)
    
    if status:
        query = query.filter(status=status)
    
    # 获取总数
    total = await query.count()
    
    # 获取分页数据
    agents = await query.offset(skip).limit(limit).order_by("-created_at").all()
    
    response = []
    for agent in agents:
        skill_count = 0
        memory_count = 0
        
        response.append({
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "status": agent.status,
            "memory_capacity": agent.memory_capacity,
            "created_at": agent.created_at.isoformat() if agent.created_at else None,
            "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
            "skill_count": skill_count,
            "memory_count": memory_count
        })
    return success_response(data={"items": response, "total": total})


@agent_router.get("/{agent_id}")
async def get_agent(agent_id: int):
    """Get agent by ID"""
    agent = await AgentService.get_agent_by_id(agent_id)
    if not agent:
        return fail_response(msg="智能体不存在", code=404)
    
    skill_count = 0
    memory_count = 0
    
    data = {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "status": agent.status,
        "memory_capacity": agent.memory_capacity,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        "skill_count": skill_count,
        "memory_count": memory_count
    }
    return success_response(data=data)


@agent_router.put("/{agent_id}")
async def update_agent(agent_id: int, agent: AgentUpdate):
    """Update agent"""
    updated_agent = await AgentService.update_agent(agent_id, agent)
    if not updated_agent:
        return fail_response(msg="智能体不存在", code=404)
    
    skill_count = 0
    memory_count = 0
    
    data = {
        "id": updated_agent.id,
        "name": updated_agent.name,
        "description": updated_agent.description,
        "status": updated_agent.status,
        "memory_capacity": updated_agent.memory_capacity,
        "created_at": updated_agent.created_at.isoformat() if updated_agent.created_at else None,
        "updated_at": updated_agent.updated_at.isoformat() if updated_agent.updated_at else None,
        "skill_count": skill_count,
        "memory_count": memory_count
    }
    return success_response(data=data, msg="智能体更新成功")


@agent_router.delete("/{agent_id}")
async def delete_agent(agent_id: int):
    """Delete agent"""
    success = await AgentService.delete_agent(agent_id)
    if not success:
        return fail_response(msg="智能体不存在", code=404)
    return success_response(msg="智能体删除成功")


@agent_router.post("/{agent_id}/execute")
async def execute_agent_unified(
    agent_id: int, 
    input_data: dict,
    stream: Optional[bool] = Query(None, description="是否强制使用流式返回"), # 前端传回来
    actor: dict = Depends(get_current_actor)  # 统一接收
):
    """
    统一智能体执行接口
    根据智能体图结构自动判断使用普通模式还是SSE模式
    
    Args:
        agent_id: 智能体ID
        input_data: 输入数据
        execution_id: 执行ID（可选）
        actor: 当前用户（从依赖注入获取）
        stream: 是否强制使用流式返回（可选）
    
    Returns:
        普通响应或SSE流式响应
    """
    try:
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            return fail_response(msg="智能体不存在", code=404)
        
        if agent.status != "active":
            return fail_response(msg="智能体未激活", code=400)
        checkpoint_service = CheckpointService.get_instance()
        # 判断是否使用SSE模式
        use_sse = stream if stream is not None else AgentService.should_use_sse(agent)
        
        if use_sse:
            # 检查是否已有正在执行的任务
            for exec_id, info in execution_manager.items():
                if info.get('agent_id') == agent_id:
                    return fail_response(msg="智能体正在执行中，请稍后再试", code=409)
            
            # 在进入SSE生成器之前，先执行预加载
            from base.plugins.agent.services.langgraph_executor import LangGraphExecutor
            flow_data = agent.graph_definition or {}
            nodes = flow_data.get("nodes", [])
            
            print(f"[API] 开始预加载资源...")
            try:
                llm_resources = await LangGraphExecutor._preload_llm_resources(nodes)
                skill_resources = await LangGraphExecutor._preload_skill_resources(nodes)
                print(f"[API] 预加载成功，LLM资源: {len(llm_resources)}, 技能资源: {len(skill_resources)}")
            except ValueError as e:
                print(f"[API] 预加载失败: {e}")
                return fail_response(msg=str(e), code=400)
            except Exception as e:
                print(f"[API] 预加载异常: {e}")
                import traceback
                traceback.print_exc()
                return fail_response(msg=f"资源预加载失败: {str(e)}", code=500)
            
            logger.info(f"[API] input_data: {input_data.get('text', '')}")
            # logger.info(f"[API] execution_id: {input_data.get('execution_id', '') or None}") 
            execution_id = input_data.get('execution_id', '')         # 生成执行ID
            execution_id = execution_id or checkpoint_service.create_thread_id(actor, execution_id)
            # logger.info(f"[API] 生成执行ID: {execution_id}")
            
            execution_manager[execution_id] = {
                'agent_id': agent_id, 
                'is_cancelled': False,
                '_llm_resources': llm_resources,
                '_skill_resources': skill_resources
            }
            
            async def sse_generator():
                try:
                    async for data in AgentService.sse_execution_generator(agent, input_data, execution_id, execution_manager, actor):
                        yield data
                finally:
                    if execution_id in execution_manager:
                        del execution_manager[execution_id]
            
            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "X-Accel-Buffering": "no"
                }
            )
        else:
            # 普通模式执行
            execution_id = input_data.get('execution_id', '') or checkpoint_service.create_thread_id(actor, '')
            result = await AgentService.execute_agent(agent_id, input_data, actor, execution_id)
            if result.get("success"):
                return success_response(data=result, msg="智能体执行成功")
            else:
                return fail_response(msg=result.get("message", "执行失败"))
    
    except Exception as e:
        import traceback
        return fail_response(msg=str(e), data={"traceback": traceback.format_exc()}, code=500)


@agent_router.get("/{agent_id}/graph")
async def get_agent_graph(agent_id: int):
    """Get agent graph definition"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== 获取智能体结构图: agent_id={agent_id} ===")
        
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            logger.error(f"智能体不存在: agent_id={agent_id}")
            return fail_response(msg="智能体不存在", code=404)
        
        logger.info(f"agent.graph_definition: {agent.graph_definition}")
        logger.info(f"agent.graph_definition 类型: {type(agent.graph_definition)}")
        
        return success_response(data={"graph_definition": agent.graph_definition})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"获取智能体结构图失败: {e}")
        return fail_response(msg=str(e))


@agent_router.put("/{agent_id}/graph")
async def update_agent_graph(agent_id: int, graph_data: dict):
    """Update agent graph definition"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"=== 保存智能体结构图: agent_id={agent_id} ===")
        logger.info(f"接收到的 graph_data: {graph_data}")
        logger.info(f"graph_data 类型: {type(graph_data)}")
        
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            logger.error(f"智能体不存在: agent_id={agent_id}")
            return fail_response(msg="智能体不存在", code=404)
        
        logger.info(f"保存前 agent.graph_definition: {agent.graph_definition}")
        
        agent.graph_definition = graph_data
        await agent.save()
        
        logger.info(f"保存后 agent.graph_definition: {agent.graph_definition}")
        logger.info(f"保存后 agent.graph_definition 类型: {type(agent.graph_definition)}")
        
        return success_response(data={"graph_definition": agent.graph_definition}, msg="智能体结构图保存成功")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"保存智能体结构图失败: {e}")
        return fail_response(msg=str(e))


@agent_router.get("/test")
async def test_endpoint():
    """测试端点"""
    print("=== 测试端点被调用 ===")
    return success_response(data={"message": "测试成功"}, msg="测试端点响应成功")


@agent_router.post("/process-documents")
async def process_documents(directory_path: str = Query(..., description="文档目录路径"), vector_store_path: str = Query(..., description="向量库存储路径")):
    """处理文档并生成向量库"""
    try:
        from base.plugins.agent.services.document_processing_service import DocumentProcessingService, VECTOR_SUPPORT
        import os
        
        # 检查向量支持是否启用
        if not VECTOR_SUPPORT:
            return fail_response(msg="向量支持未启用，请安装相关依赖", code=400)
        
        # 检查目录是否存在
        if not os.path.exists(directory_path):
            return fail_response(msg="文档目录不存在", code=404)
        
        # 确保向量库存储路径存在
        os.makedirs(vector_store_path, exist_ok=True)
        
        # 处理文档并创建向量库
        vector_store = DocumentProcessingService.process_document_directory(directory_path, vector_store_path)
        
        # 获取向量库信息
        collection_name = vector_store._collection.name
        document_count = vector_store._collection.count()
        
        return success_response(
            data={"vector_store_path": vector_store_path, "collection_name": collection_name, "document_count": document_count, "message": f"成功处理文档并生成向量库，共处理 {document_count} 个文档片段"},
            msg="文档处理成功"
        )
    except Exception as e:
        return fail_response(msg=str(e), code=500)

@execution_router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """取消执行中的任务"""
    try:
        print(f"[API] 收到取消请求，execution_id: {execution_id}")
        
        # 检查执行是否存在
        exec_info = execution_manager.get(execution_id)
        if not exec_info:
            return fail_response(msg="执行任务不存在或已结束", code=404)
        
        # 标记为取消
        exec_info['is_cancelled'] = True
        print(f"[API] 已标记任务为取消状态，execution_id: {execution_id}")
        
        return success_response(msg="取消请求已发送，执行将在安全点停止")
    except Exception as e:
        import traceback
        print(f"[API] 取消执行错误: {e}")
        print(traceback.format_exc())
        return fail_response(msg=str(e), code=500)


@execution_router.get("/")
async def list_executions():
    """列出所有正在执行的任务"""
    try:
        executions_list = []
        for exec_id, exec_info in execution_manager.items():
            executions_list.append({'execution_id': exec_id, 'agent_id': exec_info.get('agent_id'), 'is_cancelled': exec_info.get('is_cancelled', False)})
        
        return success_response(data={"executions": executions_list, "count": len(executions_list)})
    except Exception as e:
        import traceback
        print(f"[API] 列执行错误: {e}")
        print(traceback.format_exc())
        return fail_response(msg=str(e), code=500)
