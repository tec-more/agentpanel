from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from base.plugins.agent.schemas.dialog_flow import (
    DialogFlowCreate, DialogFlowUpdate, DialogFlowResponse,
    DialogFlowNodeCreate, DialogFlowNodeUpdate, DialogFlowNodeResponse,
    DialogFlowEdgeCreate, DialogFlowEdgeUpdate, DialogFlowEdgeResponse,
    DialogFlowExecutionCreate, DialogFlowExecutionResponse
)
from base.plugins.agent.services.dialog_flow_service import DialogFlowService
from base.common.response import success_response, fail_response
import uuid

dialog_flow_router = APIRouter(prefix="/dialog-flows", tags=["dialog-flows"])


@dialog_flow_router.get("/")
async def list_dialog_flows(
    name: str = Query("", description="对话流名称"),
    status: str = Query("", description="状态"),
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数")
):
    """列出对话流，可按名称或状态过滤"""
    from base.plugins.agent.models.dialog_flow import DialogFlow
    
    query = DialogFlow.all()
    
    if name:
        query = query.filter(name__icontains=name)
    
    if status:
        query = query.filter(status=status)
    
    total = await query.count()
    
    dialog_flows = await DialogFlowService.list_dialog_flows(None, skip, limit, name, status)
    
    return success_response(data={"items": dialog_flows, "total": total})


@dialog_flow_router.post("/")
async def create_dialog_flow(data: DialogFlowCreate):
    """创建新的对话流"""
    try:
        dialog_flow = await DialogFlowService.create_dialog_flow(data)
        return success_response(data=dialog_flow, msg="对话流创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@dialog_flow_router.get("/nodes/{node_id}")
async def get_node(node_id: int):
    """根据ID获取对话流节点"""
    node = await DialogFlowService.get_node(node_id)
    if not node:
        return fail_response(msg="节点不存在", code=404)
    return success_response(data=node)


@dialog_flow_router.put("/nodes/{node_id}")
async def update_node(node_id: int, data: DialogFlowNodeUpdate):
    """更新对话流节点信息"""
    node = await DialogFlowService.update_node(node_id, data)
    if not node:
        return fail_response(msg="节点不存在", code=404)
    return success_response(data=node, msg="节点更新成功")


@dialog_flow_router.delete("/nodes/{node_id}")
async def delete_node(node_id: int):
    """删除对话流节点"""
    success = await DialogFlowService.delete_node(node_id)
    if not success:
        return fail_response(msg="节点不存在", code=404)
    return success_response(msg="节点删除成功")


@dialog_flow_router.get("/edges/{edge_id}")
async def get_edge(edge_id: int):
    """根据ID获取对话流边"""
    edge = await DialogFlowService.get_edge(edge_id)
    if not edge:
        return fail_response(msg="边不存在", code=404)
    return success_response(data=edge)


@dialog_flow_router.put("/edges/{edge_id}")
async def update_edge(edge_id: int, data: DialogFlowEdgeUpdate):
    """更新对话流边信息"""
    edge = await DialogFlowService.update_edge(edge_id, data)
    if not edge:
        return fail_response(msg="边不存在", code=404)
    return success_response(data=edge, msg="边更新成功")


@dialog_flow_router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: int):
    """删除对话流边"""
    success = await DialogFlowService.delete_edge(edge_id)
    if not success:
        return fail_response(msg="边不存在", code=404)
    return success_response(msg="边删除成功")


@dialog_flow_router.post("/{dialog_flow_id}/execute")
async def execute_dialog_flow(
    dialog_flow_id: int,
    input_data: dict,
    stream: Optional[bool] = Query(None, description="是否强制使用流式返回")
):
    """
    执行对话流
    根据对话流结构自动判断使用普通模式还是SSE模式
    """
    try:
        dialog_flow = await DialogFlowService.get_dialog_flow(dialog_flow_id)
        if not dialog_flow:
            return fail_response(msg="对话流不存在", code=404)
        
        if dialog_flow.status != "active":
            return fail_response(msg="对话流未激活", code=400)
        
        use_sse = stream if stream is not None else DialogFlowService.should_use_sse(dialog_flow)
        
        if use_sse:
            execution_id = str(uuid.uuid4())
            
            async def sse_generator():
                async for data in DialogFlowService.sse_execution_generator(
                    dialog_flow, input_data, execution_id
                ):
                    yield data
            
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
            execution = await DialogFlowService.execute_dialog_flow(
                dialog_flow_id=dialog_flow_id,
                input_data=input_data
            )
            return success_response(data=execution, msg="对话流执行成功")
    
    except Exception as e:
        import traceback
        return fail_response(msg=str(e), data={"traceback": traceback.format_exc()}, code=500)


@dialog_flow_router.get("/executions")
async def list_dialog_flow_executions(
    dialog_flow_id: Optional[int] = Query(None, description="对话流ID"),
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数")
):
    """列出对话流执行记录，可按对话流ID过滤"""
    from base.plugins.agent.models.dialog_flow import DialogFlowExecution
    
    if dialog_flow_id is not None and not isinstance(dialog_flow_id, int):
        dialog_flow_id = None
    
    query = DialogFlowExecution.all()
    if dialog_flow_id:
        query = query.filter(dialog_flow_id=dialog_flow_id)
    total = await query.count()
    
    executions = await DialogFlowService.list_executions(dialog_flow_id, None, skip, limit)
    return success_response(data={"items": executions, "total": total})


@dialog_flow_router.get("/executions/{execution_id}")
async def get_dialog_flow_execution(execution_id: int):
    """根据ID获取对话流执行记录"""
    execution = await DialogFlowService.get_execution(execution_id)
    if not execution:
        return fail_response(msg="执行记录不存在", code=404)
    return success_response(data=execution)


@dialog_flow_router.get("/{dialog_flow_id}")
async def get_dialog_flow(dialog_flow_id: int):
    """根据ID获取对话流详情"""
    dialog_flow = await DialogFlowService.get_dialog_flow(dialog_flow_id)
    if not dialog_flow:
        return fail_response(msg="对话流不存在", code=404)
    return success_response(data=dialog_flow)


@dialog_flow_router.put("/{dialog_flow_id}")
async def update_dialog_flow(dialog_flow_id: int, data: DialogFlowUpdate):
    """更新对话流信息"""
    dialog_flow = await DialogFlowService.update_dialog_flow(dialog_flow_id, data)
    if not dialog_flow:
        return fail_response(msg="对话流不存在", code=404)
    return success_response(data=dialog_flow, msg="对话流更新成功")


@dialog_flow_router.delete("/{dialog_flow_id}")
async def delete_dialog_flow(dialog_flow_id: int):
    """删除对话流"""
    success = await DialogFlowService.delete_dialog_flow(dialog_flow_id)
    if not success:
        return fail_response(msg="对话流不存在", code=404)
    return success_response(msg="对话流删除成功")


@dialog_flow_router.post("/{dialog_flow_id}/nodes")
async def create_node(dialog_flow_id: int, data: DialogFlowNodeCreate):
    """在指定对话流中创建节点"""
    data.dialog_flow_id = dialog_flow_id
    try:
        node = await DialogFlowService.create_node(data)
        return success_response(data=node, msg="节点创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@dialog_flow_router.get("/{dialog_flow_id}/nodes")
async def list_nodes(dialog_flow_id: int):
    """列出指定对话流的所有节点"""
    nodes = await DialogFlowService.list_nodes(dialog_flow_id)
    return success_response(data=nodes)


@dialog_flow_router.post("/{dialog_flow_id}/edges")
async def create_edge(dialog_flow_id: int, data: DialogFlowEdgeCreate):
    """在指定对话流中创建边"""
    data.dialog_flow_id = dialog_flow_id
    try:
        edge = await DialogFlowService.create_edge(data)
        return success_response(data=edge, msg="边创建成功")
    except Exception as e:
        return fail_response(msg=str(e))


@dialog_flow_router.get("/{dialog_flow_id}/edges")
async def list_edges(dialog_flow_id: int):
    """列出指定对话流的所有边"""
    edges = await DialogFlowService.list_edges(dialog_flow_id)
    return success_response(data=edges)


@dialog_flow_router.post("/{dialog_flow_id}/langgraph-execute")
async def execute_dialog_flow_langgraph(
    dialog_flow_id: int,
    request_data: dict,
    session_id: Optional[str] = Query(None, description="会话ID，用于多轮对话"),
    user_id: Optional[int] = Query(None, description="用户ID，用于记忆管理"),
    checkpoint_id: Optional[str] = Query(None, description="检查点ID，用于恢复"),
    stream: Optional[bool] = Query(True, description="是否使用流式返回")
):
    """
    使用LangGraph执行对话流，支持多轮对话、记忆管理和Checkpoint
    """
    try:
        dialog_flow = await DialogFlowService.get_dialog_flow(dialog_flow_id)
        if not dialog_flow:
            return fail_response(msg="对话流不存在", code=404)
        
        if dialog_flow.status != "active":
            return fail_response(msg="对话流未激活", code=400)
        
        input_data = request_data.get("input_data", request_data)
        
        if stream:
            import json
            import asyncio
            from datetime import datetime
            
            async def sse_generator():
                event_queue = asyncio.Queue()
                
                async def push_event(event_data):
                    await event_queue.put(
                        f"data: {json.dumps({**event_data, 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"
                    )
                
                async def execute_flow():
                    try:
                        result = await DialogFlowService.execute_dialog_flow_with_langgraph(
                            dialog_flow_id=dialog_flow_id,
                            input_data=input_data,
                            session_id=session_id,
                            user_id=user_id,
                            checkpoint_id=checkpoint_id,
                            sse_yield_func=push_event
                        )
                        await push_event({
                            "type": "complete",
                            "data": result
                        })
                    except Exception as e:
                        import traceback
                        await push_event({
                            "type": "error",
                            "message": str(e),
                            "traceback": traceback.format_exc()
                        })
                
                task = asyncio.create_task(execute_flow())
                
                while True:
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                        yield event
                    except asyncio.TimeoutError:
                        if task.done():
                            break
                        continue
                    except Exception:
                        break
                
                if not task.done():
                    await task
            
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
            result = await DialogFlowService.execute_dialog_flow_with_langgraph(
                dialog_flow_id=dialog_flow_id,
                input_data=input_data,
                session_id=session_id,
                user_id=user_id,
                checkpoint_id=checkpoint_id
            )
            return success_response(data=result, msg="对话流执行成功")
    
    except Exception as e:
        import traceback
        return fail_response(msg=str(e), data={"traceback": traceback.format_exc()}, code=500)


@dialog_flow_router.get("/{dialog_flow_id}/checkpoints")
async def list_user_checkpoints(
    dialog_flow_id: int,
    user_id: int = Query(..., description="用户ID")
):
    """获取用户在指定对话流中的所有检查点"""
    try:
        checkpoints = await DialogFlowService.get_user_checkpoints(
            dialog_flow_id=dialog_flow_id,
            user_id=user_id
        )
        return success_response(data={"items": checkpoints, "total": len(checkpoints)})
    except Exception as e:
        return fail_response(msg=str(e), code=500)


@dialog_flow_router.get("/checkpoints/session/{session_id}")
async def list_session_checkpoints(
    session_id: str,
    user_id: int = Query(..., description="用户ID")
):
    """获取指定会话的所有检查点"""
    try:
        checkpoints = await DialogFlowService.get_session_checkpoints(
            session_id=session_id,
            user_id=user_id
        )
        return success_response(data={"items": checkpoints, "total": len(checkpoints)})
    except Exception as e:
        return fail_response(msg=str(e), code=500)


@dialog_flow_router.get("/checkpoints/{checkpoint_id}")
async def get_checkpoint_detail(
    checkpoint_id: str,
    user_id: int = Query(..., description="用户ID")
):
    """获取检查点详情"""
    try:
        checkpoint = await DialogFlowService.get_checkpoint_detail(
            checkpoint_id=checkpoint_id,
            user_id=user_id
        )
        if not checkpoint:
            return fail_response(msg="检查点不存在", code=404)
        return success_response(data=checkpoint)
    except Exception as e:
        return fail_response(msg=str(e), code=500)