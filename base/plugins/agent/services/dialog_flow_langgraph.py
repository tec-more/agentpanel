"""
对话流 LangGraph 执行器 - 复用智能体的LangGraph执行器
支持智能体的所有高级节点类型，实现能力对齐
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Annotated, TypedDict

# LangGraph 和 LangChain 相关导入
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.types import Command
from langgraph.errors import GraphInterrupt

# 本地导入
from base.plugins.agent.models.dialog_flow import DialogFlow
from base.plugins.agent.models.agent import Agent
from base.plugins.agent.utils.safe_eval import safe_eval
from base.plugins.agent.services.memory_service import MemoryService
from base.plugins.agent.services.checkpoint_service import CheckpointService
from base.plugins.agent.services.langgraph_executor import LangGraphExecutor, AgentState, last_value_reducer

logger = logging.getLogger(__name__)


class DialogFlowState(AgentState):
    """对话流执行状态，继承智能体状态"""
    dialog_flow_id: Annotated[Optional[int], last_value_reducer]
    user_id: Annotated[Optional[int], last_value_reducer]
    session_id: Annotated[Optional[str], last_value_reducer]


class DialogFlowLangGraphExecutor:
    """对话流 LangGraph 执行器 - 复用智能体执行器，支持所有高级节点类型"""

    _graph_cache = {}
    _preloaded_llm_resources = {}

    @staticmethod
    def _get_cache_key(dialog_flow_id: int) -> str:
        return f"dialog_flow_{dialog_flow_id}"

    @staticmethod
    async def execute_dialog_flow(
        dialog_flow: DialogFlow,
        input_data: Dict[str, Any],
        actor: dict = None,
        sse_yield_func=None,
        session_id: str = None,
        user_id: int = None,
        checkpoint_id: str = None
    ) -> Dict[str, Any]:
        """
        执行对话流 - 使用智能体的LangGraph执行器
        
        Args:
            dialog_flow: 对话流对象
            input_data: 输入数据
            actor: 执行者信息
            sse_yield_func: SSE推送回调函数
            session_id: 会话ID（用于多轮对话和Checkpoint）
            user_id: 用户ID（用于记忆管理）
            checkpoint_id: 检查点ID（用于恢复）
            
        Returns:
            执行结果
        """
        logger.info(f"开始执行对话流: dialog_flow_id={dialog_flow.id}, name={dialog_flow.name}")
        logger.debug(f"输入参数: {input_data}")

        try:
            flow_data = None
            if dialog_flow.flow_data:
                if isinstance(dialog_flow.flow_data, str):
                    try:
                        flow_data = json.loads(dialog_flow.flow_data)
                    except json.JSONDecodeError:
                        logger.error("对话流结构解析失败")
                        flow_data = None
                else:
                    flow_data = dialog_flow.flow_data

            if flow_data and isinstance(flow_data, dict) and flow_data.get("nodes"):
                logger.info("使用 LangGraph 执行对话流")
                result = await DialogFlowLangGraphExecutor._execute_with_langgraph(
                    dialog_flow=dialog_flow,
                    flow_data=flow_data,
                    input_data=input_data,
                    actor=actor,
                    sse_yield_func=sse_yield_func,
                    session_id=session_id,
                    user_id=user_id,
                    checkpoint_id=checkpoint_id
                )
                return result
            else:
                logger.warning("对话流没有配置节点，使用简化执行方式")
                return await DialogFlowLangGraphExecutor._execute_simple(dialog_flow, input_data)
        except Exception as e:
            logger.exception(f"执行对话流失败: {str(e)}")
            import traceback
            return {
                "success": False,
                "message": str(e),
                "traceback": traceback.format_exc()
            }

    @staticmethod
    async def _execute_with_langgraph(
        dialog_flow: DialogFlow,
        flow_data: Dict[str, Any],
        input_data: Dict[str, Any],
        actor: dict = None,
        sse_yield_func=None,
        session_id: str = None,
        user_id: int = None,
        checkpoint_id: str = None
    ) -> Dict[str, Any]:
        """
        使用智能体的LangGraph执行器执行对话流
        
        Args:
            dialog_flow: 对话流对象
            flow_data: 结构图数据
            input_data: 输入数据
            actor: 执行者信息
            sse_yield_func: SSE推送回调函数
            session_id: 会话ID
            user_id: 用户ID
            checkpoint_id: 检查点ID
            
        Returns:
            执行结果
        """
        try:
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", [])

            if not nodes:
                logger.warning("对话流没有节点，回退到简单执行")
                return await DialogFlowLangGraphExecutor._execute_simple(dialog_flow, input_data)

            cache_key = DialogFlowLangGraphExecutor._get_cache_key(dialog_flow.id)
            if cache_key not in DialogFlowLangGraphExecutor._preloaded_llm_resources:
                logger.info("[预加载] 开始预加载LLM节点资源...")
                llm_resources = await LangGraphExecutor._preload_llm_resources(nodes)
                DialogFlowLangGraphExecutor._preloaded_llm_resources[cache_key] = llm_resources
                logger.info(f"[预加载] LLM资源预加载完成，资源数: {len(llm_resources)}")
            else:
                llm_resources = DialogFlowLangGraphExecutor._preloaded_llm_resources[cache_key]
                logger.info(f"[预加载] 使用缓存的LLM资源，资源数: {len(llm_resources)}")

            skill_resources = await LangGraphExecutor._preload_skill_resources(nodes)
            logger.info(f"[预加载] 技能资源预加载完成，资源数: {len(skill_resources)}")

            memory_list = []
            if user_id:
                logger.info(f"[记忆] 加载用户记忆: user_id={user_id}")
                memory_list = await DialogFlowLangGraphExecutor._load_memory_for_user(
                    dialog_flow.id, user_id
                )
                logger.info(f"[记忆] 加载完成，共 {len(memory_list)} 条记忆")

            workflow = StateGraph(DialogFlowState)
            node_map = {node.get("id"): node for node in nodes}
            start_node = LangGraphExecutor._find_start_node(nodes)
            start_node_id = start_node.get("id", "start") if start_node else "start"

            logger.info(f"开始构建 LangGraph，节点数: {len(nodes)}, 边数: {len(edges)}")
            logger.info(f"开始节点: {start_node_id}")

            def create_node_executor(node):
                node_id = node.get("id", "")
                node_type = node.get("type", "")
                async def node_executor(state: Dict[str, Any]):
                    logger.info(f"节点执行器被调用: {node_id} ({node_type})")
                    
                    original_flow_data = state.get("flow_data")
                    
                    result = await DialogFlowLangGraphExecutor._execute_node_with_logging(
                        node, state, 
                        llm_resources=llm_resources, 
                        skill_resources=skill_resources,
                        sse_yield_func=sse_yield_func
                    )
                    
                    if original_flow_data is not None and "flow_data" not in result:
                        result["flow_data"] = original_flow_data
                    
                    return result
                return node_executor

            for node in nodes:
                node_id = node.get("id", "")
                node_type = node.get("type", "")
                if not node_id:
                    continue
                workflow.add_node(node_id, create_node_executor(node))

            edge_map = {}
            for edge in edges:
                source = edge.get("source", "")
                target = edge.get("target", "")
                if source and target:
                    edge_map[source] = target

            if start_node_id in node_map:
                workflow.add_edge(START, start_node_id)

            condition_edges = {}
            for edge in edges:
                source = edge.get("source", "")
                target = edge.get("target", "")
                if source and target:
                    source_node = node_map.get(source)
                    if source_node and source_node.get("type") == "condition":
                        if source not in condition_edges:
                            condition_edges[source] = []
                        condition_edges[source].append(edge)
                    else:
                        workflow.add_edge(source, target)

            import re
            
            for condition_node_id, edge_list in condition_edges.items():
                def create_condition_router(node_id, edges):
                    async def condition_router(state: Dict[str, Any]):
                        variables = state.get("variables", {})
                        
                        conditional_edges = []
                        default_edges = []
                        
                        for edge in edges:
                            condition = edge.get("condition", "").strip()
                            if condition:
                                conditional_edges.append(edge)
                            else:
                                default_edges.append(edge)
                        
                        conditional_edges.sort(key=lambda x: x.get("priority", 0))
                        
                        for edge in conditional_edges:
                            if not edge.get("enabled", True):
                                continue
                                
                            condition = edge.get("condition", "")
                            edge_target = edge.get("target", "")
                            
                            try:
                                def get_var(data, *keys):
                                    for key in keys:
                                        if data is None or not isinstance(data, dict):
                                            return None
                                        data = data.get(key, None)
                                    return data
                                
                                def replace_template(match):
                                    path = match.group(1)
                                    parts = path.split('.')
                                    result = "get_var(variables"
                                    for part in parts:
                                        result += f", '{part}'"
                                    result += ")"
                                    return result
                                
                                expr = re.sub(r'\{\{(\w+(\.\w+)*)\}\}', replace_template, condition)
                                result = safe_eval(expr, {"variables": variables, "get_var": get_var})
                                
                                if result:
                                    return edge_target
                            except Exception as e:
                                logger.warning(f"条件表达式执行失败 [{edge.get('id')}]: {e}")
                        
                        if default_edges:
                            default_edges.sort(key=lambda x: x.get("priority", 0))
                            return default_edges[0].get("target")
                        
                        return END
                    return condition_router

                workflow.add_conditional_edges(
                    condition_node_id,
                    create_condition_router(condition_node_id, edge_list),
                    [e.get("target") for e in edge_list]
                )

            for node in nodes:
                if node.get("type") == "end":
                    node_id = node.get("id", "")
                    if node_id:
                        workflow.add_edge(node_id, END)

            if start_node_id not in node_map:
                raise ValueError(f"开始节点 {start_node_id} 不在节点映射中")

            initial_state: Dict[str, Any] = {
                "input": input_data,
                "output": {},
                "messages": [],
                "variables": {
                    "dialog_flow_id": dialog_flow.id,
                    "dialog_flow_name": dialog_flow.name,
                    "session_id": session_id,
                    "user_id": user_id,
                    "recent_memories": memory_list,
                    "_llm_resources": llm_resources,
                    "_skill_resources": skill_resources
                },
                "node_results": {},
                "execution_trace": [],
                "current_node": None,
                "error": None,
                "flow_data": flow_data,
                "dialog_flow_id": dialog_flow.id,
                "user_id": user_id,
                "session_id": session_id
            }

            checkpoint_service = CheckpointService.get_instance()
            checkpointer = checkpoint_service.get_checkpointer()
            
            if not actor:
                actor = {"id": user_id or "anonymous", "type": "user"}
            
            config = checkpoint_service.build_config(
                actor=actor,
                execution_id=session_id,
                checkpoint_id=checkpoint_id,
                dialog_flow_id=dialog_flow.id,
                dialog_flow_name=dialog_flow.name
            )

            graph_with_memory = workflow.compile(checkpointer=checkpointer)
            final_state = await graph_with_memory.ainvoke(initial_state, config=config)

            if user_id:
                await DialogFlowLangGraphExecutor._save_dialog_memory(
                    dialog_flow_id=dialog_flow.id,
                    user_id=user_id,
                    input_data=input_data,
                    variables=final_state.get("variables", {})
                )

            result = {
                "success": True,
                "message": "执行成功",
                "input": input_data,
                "output": final_state.get("output", {}),
                "variables": final_state.get("variables", {}),
                "execution_trace": final_state.get("execution_trace", []),
                "node_results": final_state.get("node_results", {}),
                "messages": final_state.get("messages", []),
                "session_id": session_id,
                "error": final_state.get("error")
            }

            return result

        except Exception as e:
            logger.exception(f"LangGraph 执行失败: {e}")
            import traceback
            return {
                "success": False,
                "message": str(e),
                "traceback": traceback.format_exc()
            }

    @staticmethod
    async def _execute_node_with_logging(current_node, state, llm_resources=None, skill_resources=None, sse_yield_func=None):
        """执行节点，支持智能体的所有节点类型"""
        node_id = current_node.get("id", "")
        node_type = current_node.get("type")
        node_data = current_node.get("data", {})
        node_label = node_data.get("label", node_type)

        logger.info(f"执行节点 [{node_id}]: {node_type}")
        
        original_flow_data = state.get("flow_data")
        state["current_node"] = node_label

        if "execution_trace" not in state:
            state["execution_trace"] = []
        step_count = len(state["execution_trace"]) + 1

        if sse_yield_func:
            try:
                await sse_yield_func({
                    'type': 'node_start',
                    'node_id': node_id,
                    'node_type': node_type,
                    'node_label': node_label,
                    'step': step_count
                })
            except Exception as e:
                logger.warning(f"推送节点开始事件失败: {e}")

        try:
            if node_type == "start":
                if sse_yield_func:
                    await sse_yield_func({'type': 'info', 'label': '开始节点', 'message': '开始执行...'})
                state = await LangGraphExecutor._execute_start_node(node_data, state)
            elif node_type == "end":
                if sse_yield_func:
                    await sse_yield_func({'type': 'info', 'label': '结束节点', 'message': '执行结束'})
                state = await LangGraphExecutor._execute_end_node(node_data, state)
            elif node_type == "input":
                state = await DialogFlowLangGraphExecutor._execute_input_node(node_data, state)
            elif node_type == "output":
                state = await DialogFlowLangGraphExecutor._execute_output_node(node_data, state)
            elif node_type == "llm":
                stream_val = node_data.get("llm_stream", False)
                is_streaming = stream_val is True or (isinstance(stream_val, str) and stream_val.lower() == 'true')
                if sse_yield_func:
                    await sse_yield_func({'type': 'thinking', 'label': node_label, 'message': '正在调用大模型...'})
                if is_streaming and sse_yield_func:
                    state = await DialogFlowLangGraphExecutor._execute_llm_node_streaming(
                        current_node, state, llm_resources=llm_resources, sse_yield_func=sse_yield_func
                    )
                else:
                    state = await DialogFlowLangGraphExecutor._execute_llm_node(
                        current_node, state, llm_resources=llm_resources
                    )
            elif node_type == "knowledge_retrieval":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': '正在检索知识...'})
                state = await DialogFlowLangGraphExecutor._execute_knowledge_retrieval_node(node_data, state)
            elif node_type == "api":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': '正在调用API...'})
                state = await DialogFlowLangGraphExecutor._execute_api_node(node_data, state)
            elif node_type == "message":
                if sse_yield_func:
                    await sse_yield_func({'type': 'message', 'content': node_data.get('content', '')})
                state = await DialogFlowLangGraphExecutor._execute_message_node(node_data, state)
            elif node_type == "text":
                state = await DialogFlowLangGraphExecutor._execute_text_node(node_data, state)
            elif node_type == "image":
                if sse_yield_func:
                    await sse_yield_func({'type': 'image', 'image_url': node_data.get('image_url', '')})
                state = await DialogFlowLangGraphExecutor._execute_image_node(node_data, state)
            elif node_type == "voice":
                if sse_yield_func:
                    await sse_yield_func({'type': 'voice', 'message': '正在处理语音...'})
                state = await DialogFlowLangGraphExecutor._execute_voice_node(node_data, state)
            elif node_type == "condition":
                if sse_yield_func:
                    await sse_yield_func({'type': 'thinking', 'label': node_label, 'message': '条件判断中...'})
                state = await LangGraphExecutor._execute_condition_node(node_data, state)
            elif node_type == "question":
                state = await DialogFlowLangGraphExecutor._execute_question_node(node_data, state)
            elif node_type == "skill":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': f'执行技能: {node_data.get("skill_id", "unknown")}'})
                state = await LangGraphExecutor._execute_skill_node(node_data, state)
            elif node_type == "tool":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': f'执行工具: {node_data.get("tool_name", "unknown")}'})
                processed_node_data = DialogFlowLangGraphExecutor._process_tool_node_data(node_data)
                state = await LangGraphExecutor._execute_tool_node(processed_node_data, state)
            elif node_type == "http":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': '发送HTTP请求'})
                state = await LangGraphExecutor._execute_http_node(node_data, state)
            elif node_type == "code":
                state = await LangGraphExecutor._execute_code_node(node_data, state)
            elif node_type == "template":
                state = await LangGraphExecutor._execute_template_node(node_data, state)
            elif node_type == "loop":
                state = await LangGraphExecutor._execute_loop_node(node_data, state)
            elif node_type == "iteration":
                state = await LangGraphExecutor._execute_iteration_node(node_data, state)
            elif node_type == "parallel":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': '并行执行分支任务...'})
                state = await LangGraphExecutor._execute_parallel_node(current_node, state)
            elif node_type == "variable_aggregator":
                state = await LangGraphExecutor._execute_variable_aggregator_node(node_data, state)
            elif node_type == "variable_assigner":
                state = await LangGraphExecutor._execute_variable_assigner_node(node_data, state)
            elif node_type == "parameter_extractor":
                state = await LangGraphExecutor._execute_parameter_extractor_node(node_data, state)
            elif node_type == "json_extractor":
                state = await LangGraphExecutor._execute_json_extractor_node(node_data, state)
            elif node_type == "document_extractor":
                state = await LangGraphExecutor._execute_document_extractor_node(node_data, state)
            elif node_type == "agent":
                state = await LangGraphExecutor._execute_agent_node(node_data, state)
            else:
                state = await LangGraphExecutor._execute_default_node(node_data, state)

            state["execution_trace"].append({
                "node_id": node_id,
                "node_type": node_type,
                "label": node_label,
                "timestamp": datetime.now().isoformat()
            })

            if sse_yield_func:
                try:
                    await sse_yield_func({
                        'type': 'node_complete',
                        'node_id': node_id,
                        'node_type': node_type,
                        'node_label': node_label
                    })
                except Exception as e:
                    logger.warning(f"推送节点完成事件失败: {e}")

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.exception(f"节点执行失败: {e}")
            state["error"] = str(e)
            if sse_yield_func:
                await sse_yield_func({'type': 'error', 'node_id': node_id, 'message': str(e)})

        if original_flow_data is not None and "flow_data" not in state:
            state["flow_data"] = original_flow_data

        return state

    @staticmethod
    async def _load_memory_for_user(dialog_flow_id: int, user_id: int) -> List[Dict[str, Any]]:
        """加载用户记忆"""
        try:
            memories = await MemoryService.get_memories_by_agent(
                agent_id=dialog_flow_id,
                memory_mode="private",
                user_id=user_id
            )
            memory_list = []
            for m in memories:
                memory_list.append({
                    "id": m.id,
                    "content": m.content,
                    "type": m.type,
                    "importance": m.importance,
                    "created_at": m.created_at.isoformat() if m.created_at else None
                })
            return memory_list
        except Exception as e:
            logger.warning(f"加载用户记忆失败: {e}")
            return []

    @staticmethod
    async def _save_dialog_memory(dialog_flow_id: int, user_id: int, input_data: Dict[str, Any], variables: Dict[str, Any]):
        """保存对话记忆"""
        try:
            from base.plugins.agent.schemas.memory import MemoryCreate

            memory_mode = "private"
            user_id_val = user_id

            input_text = input_data.get("text", "")
            if input_text and user_id_val:
                input_memory_data = MemoryCreate(
                    agent_id=dialog_flow_id,
                    content=f"用户输入: {input_text}",
                    type="short_term",
                    importance=0.8,
                    memory_mode=memory_mode,
                    user_id=user_id_val
                )
                await MemoryService.create_memory(input_memory_data)

            key_variables = [
                "response", "output", "result", "text",
                "summary", "answer", "reply", "content",
                "knowledge_result", "api_result",
                "final_output", "output_data"
            ]

            saved_vars = set()
            for var_name in key_variables:
                if var_name in variables and var_name not in saved_vars:
                    value = variables[var_name]
                    content_str = ""
                    if isinstance(value, dict):
                        content_str = json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, list):
                        content_str = json.dumps(value, ensure_ascii=False)
                    else:
                        content_str = str(value)

                    if content_str and len(content_str.strip()) > 0 and len(content_str) < 5000 and user_id_val:
                        try:
                            importance = 0.9 if var_name in ["final_output", "response", "answer"] else 0.7
                            memory_data = MemoryCreate(
                                agent_id=dialog_flow_id,
                                content=f"{var_name}: {content_str}",
                                type="long_term",
                                importance=importance,
                                memory_mode=memory_mode,
                                user_id=user_id_val
                            )
                            await MemoryService.create_memory(memory_data)
                            saved_vars.add(var_name)
                        except Exception as e:
                            logger.warning(f"保存记忆失败 {var_name}: {e}")

        except Exception as e:
            logger.warning(f"保存对话流记忆时出错: {e}")

    @staticmethod
    async def _execute_simple(dialog_flow: DialogFlow, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """简化执行方式"""
        input_text = input_data.get("text", "")
        return {
            "success": True,
            "message": "执行成功",
            "input": input_data,
            "output": {"text": f"已处理: {input_text}"}
        }

    @staticmethod
    async def _execute_input_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行输入节点 - 支持多模态输入"""
        input_key = node_data.get("input_var", "input")
        input_data = state.get("input", {})
        input_types = node_data.get("input_types", ["text"])
        
        if isinstance(input_types, str):
            input_types = [input_types]
        
        output = {input_key: input_data.get("text", "")}
        
        if "text" in input_types:
            output["input_text"] = input_data.get("text", "")
        
        if "image" in input_types:
            image_urls = input_data.get("image_urls", [])
            if isinstance(image_urls, str):
                image_urls = [image_urls] if image_urls else []
            output["input_image_urls"] = image_urls
            if image_urls:
                output["input_image_url"] = image_urls[0]
        
        if "voice" in input_types:
            audio_urls = input_data.get("audio_urls", [])
            if isinstance(audio_urls, str):
                audio_urls = [audio_urls] if audio_urls else []
            output["input_audio_urls"] = audio_urls
            if audio_urls:
                output["input_audio_url"] = audio_urls[0]
        
        state["variables"].update(output)
        state["node_results"]["input"] = output
        return state

    @staticmethod
    async def _execute_output_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行输出节点"""
        output_var = node_data.get("output_var", "output")
        variables = state.get("variables", {})
        output_content = node_data.get("output_content", "")
        output_type = node_data.get("output_type", "text")
        
        if output_content:
            output_content = LangGraphExecutor._replace_variables(output_content, variables)
        else:
            output_content = variables.get(output_var, "")
        
        state["output"][output_var] = output_content
        state["output"]["output_type"] = output_type
        state["node_results"]["output"] = {
            "content": output_content,
            "type": output_type,
            "var": output_var
        }
        return state

    @staticmethod
    async def _execute_llm_node(current_node: Dict, state: Dict[str, Any], llm_resources: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行大模型节点（非流式）"""
        from base.plugins.llm.services.chat_service import ChatService
        
        node_data = current_node.get("data", {})
        node_id = current_node.get("id", "")
        variables = state.get("variables", {})
        input_data = state.get("input", {})
        
        prompt = node_data.get("llm_prompt", "")
        temperature = node_data.get("llm_temperature", 0.7)
        max_tokens = node_data.get("llm_max_tokens", 1024)
        output_var = node_data.get("output_var", "response")
        
        prompt = LangGraphExecutor._replace_variables(prompt, variables)
        
        image_urls = DialogFlowLangGraphExecutor._extract_image_urls(variables, input_data)
        
        llm_resource = llm_resources.get(node_id) if llm_resources else None
        if not llm_resource:
            state["variables"][output_var] = "请先配置大模型"
            state["node_results"][node_id] = {"error": "未配置大模型"}
            return state
        
        model = llm_resource["model"]
        api_key_obj = llm_resource["api_key"]
        provider = llm_resource["provider"]
        
        if not api_key_obj:
            state["variables"][output_var] = "没有可用的API密钥"
            state["node_results"][node_id] = {"error": "没有可用的API密钥"}
            return state
        
        try:
            endpoint_url = model.endpoint_url or api_key_obj.endpoint_url or provider.official_url
            if endpoint_url:
                endpoint_url = endpoint_url.rstrip('/')
                if endpoint_url.endswith('/chat/completions'):
                    endpoint_url = endpoint_url[:-len('/chat/completions')]
            
            credentials = api_key_obj.get_credentials()
            
            service = await ChatService.get_provider_service(
                provider_name_en=provider.name_en,
                api_key=credentials.get("api_key", ""),
                endpoint_url=endpoint_url,
                api_secret=credentials.get("api_secret", ""),
                call_mode=credentials.get("call_mode", "vendor_sdk"),
            )
            
            messages = []
            if input_data.get("history"):
                for msg in input_data["history"]:
                    msg_content = msg.get("content")
                    messages.append({"role": msg.get("role"), "content": msg_content})
            
            if image_urls and model.supports_vision:
                content = [{"type": "text", "text": prompt}]
                for img_url in image_urls:
                    content.append({"type": "image_url", "image_url": {"url": img_url}})
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "user", "content": prompt})
            
            result = await service.chat(
                model=model.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=1.0,
                stream=False
            )
            
            response_text = result["choices"][0]["message"]["content"]
            state["variables"][output_var] = response_text
            state["node_results"][node_id] = {
                "response": response_text,
                "model": model.model_name,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"大模型节点执行失败: {e}", exc_info=True)
            error_msg = f"大模型调用失败: {str(e)}"
            state["variables"][output_var] = error_msg
            state["node_results"][node_id] = {"error": error_msg}
        
        return state

    @staticmethod
    async def _execute_llm_node_streaming(current_node: Dict, state: Dict[str, Any], llm_resources: Dict[str, Any] = None, sse_yield_func=None) -> Dict[str, Any]:
        """执行大模型节点（流式）"""
        from base.plugins.llm.services.chat_service import ChatService
        
        node_data = current_node.get("data", {})
        node_id = current_node.get("id", "")
        variables = state.get("variables", {})
        input_data = state.get("input", {})
        
        prompt = node_data.get("llm_prompt", "")
        temperature = node_data.get("llm_temperature", 0.7)
        max_tokens = node_data.get("llm_max_tokens", 1024)
        output_var = node_data.get("output_var", "response")
        
        prompt = LangGraphExecutor._replace_variables(prompt, variables)
        
        image_urls = DialogFlowLangGraphExecutor._extract_image_urls(variables, input_data)
        
        llm_resource = llm_resources.get(node_id) if llm_resources else None
        if not llm_resource:
            state["variables"][output_var] = "请先配置大模型"
            state["node_results"][node_id] = {"error": "未配置大模型"}
            return state
        
        model = llm_resource["model"]
        api_key_obj = llm_resource["api_key"]
        provider = llm_resource["provider"]
        
        if not api_key_obj:
            state["variables"][output_var] = "没有可用的API密钥"
            state["node_results"][node_id] = {"error": "没有可用的API密钥"}
            return state
        
        try:
            endpoint_url = model.endpoint_url or api_key_obj.endpoint_url or provider.official_url
            if endpoint_url:
                endpoint_url = endpoint_url.rstrip('/')
                if endpoint_url.endswith('/chat/completions'):
                    endpoint_url = endpoint_url[:-len('/chat/completions')]
            
            credentials = api_key_obj.get_credentials()
            
            service = await ChatService.get_provider_service(
                provider_name_en=provider.name_en,
                api_key=credentials.get("api_key", ""),
                endpoint_url=endpoint_url,
                api_secret=credentials.get("api_secret", ""),
                call_mode=credentials.get("call_mode", "vendor_sdk"),
            )
            
            messages = []
            if input_data.get("history"):
                for msg in input_data["history"]:
                    msg_content = msg.get("content")
                    messages.append({"role": msg.get("role"), "content": msg_content})
            
            if image_urls and model.supports_vision:
                content = [{"type": "text", "text": prompt}]
                for img_url in image_urls:
                    content.append({"type": "image_url", "image_url": {"url": img_url}})
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "user", "content": prompt})
            
            full_response = ""
            async for chunk in service.chat_stream(
                model=model.model_id,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=1.0
            ):
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_response += content
                    if sse_yield_func:
                        await sse_yield_func({
                            "type": "stream",
                            "node_id": node_id,
                            "content": content,
                            "full_content": full_response
                        })
            
            state["variables"][output_var] = full_response
            state["node_results"][node_id] = {
                "response": full_response,
                "model": model.model_name,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"大模型节点执行失败: {e}", exc_info=True)
            error_msg = f"大模型调用失败: {str(e)}"
            state["variables"][output_var] = error_msg
            state["node_results"][node_id] = {"error": error_msg}
        
        return state

    @staticmethod
    def _extract_image_urls(variables: Dict[str, Any], input_data: Dict[str, Any]) -> List[str]:
        """提取图片URL"""
        image_urls = []
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg')
        
        for key, value in variables.items():
            if isinstance(value, str) and value:
                lower_val = value.lower()
                if key in ('image_url', 'image', 'img', 'picture', 'photo', 'input_image_url') or \
                   any(lower_val.endswith(ext) for ext in image_extensions) or \
                   ('http' in lower_val and any(ext in lower_val for ext in image_extensions)):
                    image_urls.append(value)
        
        if input_data:
            if isinstance(input_data.get('image_url'), str):
                image_urls.append(input_data['image_url'])
            elif isinstance(input_data.get('image_urls'), list):
                image_urls.extend([u for u in input_data['image_urls'] if isinstance(u, str)])
        
        if variables.get('input_image_urls'):
            image_urls.extend([u for u in variables['input_image_urls'] if isinstance(u, str)])
        
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url and url not in seen:
                seen.add(url)
                unique_urls.append(url)
        return unique_urls

    @staticmethod
    async def _execute_knowledge_retrieval_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行知识检索节点"""
        variables = state.get("variables", {})
        query = node_data.get("query", "")
        top_k = node_data.get("top_k", 5)
        output_var = node_data.get("output_var", "knowledge")
        
        query = LangGraphExecutor._replace_variables(query, variables)
        
        try:
            from base.plugins.agent.services.rag_service import RAGService
            results = await RAGService.search(query, top_k=top_k)
            contexts = [r.get("content", "") for r in results]
            result = {"results": results, "contexts": "\n".join(contexts)}
            
            state["variables"][output_var] = result
            state["node_results"]["knowledge_retrieval"] = result
        except Exception as e:
            logger.error(f"知识检索失败: {e}", exc_info=True)
            state["variables"][output_var] = f"知识检索失败: {str(e)}"
            state["node_results"]["knowledge_retrieval"] = {"error": str(e)}
        
        return state

    @staticmethod
    async def _execute_api_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行API调用节点"""
        variables = state.get("variables", {})
        url = node_data.get("url", "")
        method = node_data.get("method", "GET")
        headers = node_data.get("headers", {})
        body = node_data.get("body", {})
        output_var = node_data.get("output_var", "api_result")
        
        url = LangGraphExecutor._replace_variables(url, variables)
        
        if isinstance(body, str):
            body = LangGraphExecutor._replace_variables(body, variables)
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers if isinstance(headers, dict) else {},
                    json=body if isinstance(body, dict) else None,
                    data=body if isinstance(body, str) else None
                ) as response:
                    status = response.status
                    try:
                        result = await response.json()
                    except Exception:
                        result = await response.text()
                    
                    state["variables"][output_var] = {"status": status, "result": result}
                    state["node_results"]["api"] = {"status": status, "result": result}
        except Exception as e:
            logger.error(f"API调用失败: {e}", exc_info=True)
            state["variables"][output_var] = f"API调用失败: {str(e)}"
            state["node_results"]["api"] = {"error": str(e)}
        
        return state

    @staticmethod
    async def _execute_message_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行消息节点"""
        variables = state.get("variables", {})
        content = node_data.get("content", "")
        content = LangGraphExecutor._replace_variables(content, variables)
        message_type = node_data.get("message_type", "text")
        
        state["variables"]["last_message"] = content
        state["variables"]["last_message_type"] = message_type
        state["node_results"]["message"] = {
            "content": content,
            "message_type": message_type
        }
        
        state["messages"].append({
            "role": "assistant",
            "content": content,
            "type": message_type
        })
        
        return state

    @staticmethod
    async def _execute_text_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行文本节点"""
        variables = state.get("variables", {})
        content = node_data.get("content", "")
        content = LangGraphExecutor._replace_variables(content, variables)
        output_var = node_data.get("output_var", "text")
        
        state["variables"][output_var] = content
        state["node_results"]["text"] = {"content": content}
        
        return state

    @staticmethod
    async def _execute_image_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行图片节点"""
        variables = state.get("variables", {})
        image_url = node_data.get("image_url", "")
        image_url = LangGraphExecutor._replace_variables(image_url, variables)
        image_alt = node_data.get("image_alt", "")
        analyze_image = node_data.get("analyze_image", False)
        
        state["variables"]["image_url"] = image_url
        state["variables"]["image_alt"] = image_alt
        state["node_results"]["image"] = {
            "image_url": image_url,
            "image_alt": image_alt,
            "analyze_image": analyze_image
        }
        
        if analyze_image and image_url:
            try:
                analysis = await DialogFlowLangGraphExecutor._analyze_image_with_llm(image_url, node_data, variables)
                state["variables"]["image_analysis"] = analysis
                state["node_results"]["image"]["analysis"] = analysis
            except Exception as e:
                logger.error(f"图片分析失败: {e}")
                state["node_results"]["image"]["analysis_error"] = str(e)
        
        return state

    @staticmethod
    async def _analyze_image_with_llm(image_url: str, node_data: Dict, variables: Dict[str, Any]) -> Dict[str, Any]:
        """使用大模型分析图片"""
        from base.plugins.llm.models.model import LLMModel
        from base.plugins.llm.models.api_key import LLMApiKey
        from base.plugins.llm.services.chat_service import ChatService
        
        llm_model_id = node_data.get("llm_model_id")
        if not llm_model_id:
            return {"error": "未配置分析图片的大模型"}
        
        model = await LLMModel.get_or_none(id=llm_model_id).prefetch_related('provider')
        if not model or model.status != "active":
            return {"error": "模型不存在或未启用"}
        
        if not model.supports_vision:
            return {"error": "模型不支持视觉"}
        
        api_key_obj = await LLMApiKey.filter(model_id=model.id).first()
        if not api_key_obj:
            api_key_obj = await LLMApiKey.filter(
                provider_id=model.provider_id,
                model_id__isnull=True
            ).first()
        if not api_key_obj:
            return {"error": "没有可用的API密钥"}
        
        endpoint_url = model.endpoint_url or api_key_obj.endpoint_url or model.provider.official_url
        if endpoint_url:
            endpoint_url = endpoint_url.rstrip('/')
            if endpoint_url.endswith('/chat/completions'):
                endpoint_url = endpoint_url[:-len('/chat/completions')]
        
        credentials = api_key_obj.get_credentials()
        
        service = await ChatService.get_provider_service(
            provider_name_en=model.provider.name_en,
            api_key=credentials.get("api_key", ""),
            endpoint_url=endpoint_url,
            api_secret=credentials.get("api_secret", ""),
            call_mode=credentials.get("call_mode", "vendor_sdk"),
        )
        
        analysis_prompt = node_data.get("analysis_prompt", "请描述这张图片的内容")
        analysis_prompt = LangGraphExecutor._replace_variables(analysis_prompt, variables)
        
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": analysis_prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]
        
        result = await service.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            stream=False
        )
        
        response_text = result["choices"][0]["message"]["content"]
        return {"analysis": response_text}

    @staticmethod
    async def _execute_voice_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行语音节点"""
        variables = state.get("variables", {})
        voice_type = node_data.get("voice_type", "tts")
        language = node_data.get("language", "zh")
        voice_provider_id = node_data.get("voice_provider_id")
        
        state["variables"]["voice_type"] = voice_type
        state["variables"]["language"] = language
        state["node_results"]["voice"] = {
            "voice_type": voice_type,
            "language": language
        }
        
        if voice_type == "tts":
            text = node_data.get("text", "")
            text = LangGraphExecutor._replace_variables(text, variables)
            try:
                audio_url = await DialogFlowLangGraphExecutor._execute_voice_tts(
                    text, voice_provider_id, language
                )
                state["variables"]["audio_url"] = audio_url
                state["node_results"]["voice"]["audio_url"] = audio_url
                state["node_results"]["voice"]["text"] = text
            except Exception as e:
                logger.error(f"TTS失败: {e}")
                state["node_results"]["voice"]["error"] = str(e)
        elif voice_type == "asr":
            audio_url = node_data.get("audio_url", "")
            audio_url = LangGraphExecutor._replace_variables(audio_url, variables)
            if not audio_url and variables.get("input_audio_url"):
                audio_url = variables["input_audio_url"]
            
            if audio_url:
                try:
                    recognized_text = await DialogFlowLangGraphExecutor._execute_voice_asr(
                        audio_url, voice_provider_id, language
                    )
                    state["variables"]["recognized_text"] = recognized_text
                    state["node_results"]["voice"]["recognized_text"] = recognized_text
                    state["node_results"]["voice"]["audio_url"] = audio_url
                except Exception as e:
                    logger.error(f"ASR失败: {e}")
                    state["node_results"]["voice"]["error"] = str(e)
        
        return state

    @staticmethod
    async def _execute_voice_tts(text: str, voice_provider_id: int = None, language: str = "zh") -> str:
        """执行TTS语音合成"""
        try:
            from base.plugins.llm.services.voice_helper import VoiceServiceHelper
            
            if not text or not voice_provider_id:
                return ""
            
            service = await VoiceServiceHelper.get_voice_service(voice_provider_id)
            
            audio_bytes = await service.text_to_speech(
                text=text,
                voice="zhichu",
                language=language,
                format="mp3"
            )
            
            import os
            import uuid
            from datetime import datetime
            
            audio_dir = os.path.join(os.path.dirname(__file__), "../../../", "uploads", "audio")
            os.makedirs(audio_dir, exist_ok=True)
            
            date_dir = datetime.now().strftime("%Y/%m/%d")
            save_dir = os.path.join(audio_dir, date_dir)
            os.makedirs(save_dir, exist_ok=True)
            
            file_name = f"{uuid.uuid4()}.mp3"
            file_path = os.path.join(save_dir, file_name)
            
            with open(file_path, "wb") as f:
                f.write(audio_bytes)
            
            audio_url = f"/api/v1/upload/audio/{date_dir}/{file_name}"
            return audio_url
            
        except Exception as e:
            logger.error(f"TTS失败: {e}")
            return ""

    @staticmethod
    async def _execute_voice_asr(audio_url: str, voice_provider_id: int = None, language: str = "zh") -> str:
        """执行ASR语音识别"""
        try:
            from base.plugins.llm.services.voice_helper import VoiceServiceHelper
            
            if not audio_url or not voice_provider_id:
                return ""
            
            service = await VoiceServiceHelper.get_voice_service(voice_provider_id)
            
            result = await service.file_asr(
                audio_file=audio_url,
                format="mp3",
                language=language
            )
            
            return result.get("text", "")
            
        except Exception as e:
            logger.error(f"ASR失败: {e}")
            return ""

    @staticmethod
    def _process_tool_node_data(node_data: Dict) -> Dict:
        """处理工具节点数据，确保tool_params是字典格式"""
        processed = node_data.copy()
        
        tool_params = processed.get("tool_params", {})
        if isinstance(tool_params, str):
            try:
                processed["tool_params"] = json.loads(tool_params)
            except json.JSONDecodeError:
                logger.warning(f"工具参数解析失败，使用空字典: {tool_params}")
                processed["tool_params"] = {}
        
        return processed

    @staticmethod
    async def _execute_question_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行问题节点"""
        variables = state.get("variables", {})
        question = node_data.get("question", "")
        question = LangGraphExecutor._replace_variables(question, variables)
        variable = node_data.get("variable", "answer")
        options = node_data.get("options", "")
        
        state["variables"]["question"] = question
        state["variables"]["options"] = options
        state["node_results"]["question"] = {
            "question": question,
            "variable": variable,
            "options": options
        }
        
        return state
