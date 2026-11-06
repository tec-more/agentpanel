"""
LangGraph 执行器 - 使用真正的 LangGraph 执行智能体结构图
"""
import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from operator import add
from typing import Dict, Any, List, Optional, Annotated, TypedDict

from tortoise.exceptions import DoesNotExist


# LangGraph 和 LangChain 相关导入
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.channels import NamedBarrierValue, Topic, LastValue
from langgraph.types import Command, interrupt
from langgraph.errors import GraphInterrupt

# 本地导入
from base.plugins.agent.models.agent import Agent
from base.plugins.agent.utils.safe_eval import safe_eval
from base.plugins.agent.services.memory_service import MemoryService
from base.plugins.agent.services.checkpoint_service import CheckpointService

logger = logging.getLogger(__name__)


def dict_merge_reducer(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """字典合并reducer，支持并发更新"""
    result = left.copy()
    result.update(right)
    return result


def last_value_reducer(left, right):
    """最后值reducer，保留最后一个值"""
    return right if right is not None else left

class AgentState(TypedDict):
    """智能体执行状态，支持并发更新"""
    input: Annotated[Dict[str, Any], dict_merge_reducer]
    output: Annotated[Dict[str, Any], dict_merge_reducer]
    messages: Annotated[List[Dict[str, Any]], add]
    variables: Annotated[Dict[str, Any], dict_merge_reducer]
    node_results: Annotated[Dict[str, Any], dict_merge_reducer]
    execution_trace: Annotated[List[Dict[str, Any]], add]
    current_node: Annotated[Optional[str], last_value_reducer]
    error: Annotated[Optional[str], last_value_reducer]
    flow_data: Annotated[Dict[str, Any], dict_merge_reducer]  # 图结构数据（nodes, edges）

def create_initial_state(input_data: Dict[str, Any], agent) -> Dict[str, Any]:
    """创建初始状态"""
    return {
        "input": input_data,
        "output": {},
        "messages": [],
        "variables": {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "recent_memories": [],
            "important_memories": []
        },
        "node_results": {},
        "execution_trace": [],
        "current_node": None,
        "error": None,
        "agent": agent
    }


class LangGraphExecutor:
    """LangGraph 执行器 - 使用真正的 LangGraph 执行智能体结构图"""

    _memory_cache = {}

    @staticmethod
    async def execute_agent(
        agent: Agent,
        input_data: Dict[str, Any],
        actor: dict,
        sse_yield_func=None,
        execution_id: Optional[str] = None,
        llm_resources: Optional[Dict] = None,
        skill_resources: Optional[Dict] = None,
        execution_context=None
    ) -> Dict[str, Any]:
        """
        执行智能体
        
        Args:
            agent: 智能体对象
            input_data: 输入数据
            actor: 智能体体（客户或用户）
            sse_yield_func: SSE推送回调函数
            execution_id: 执行ID（用于追踪）
            llm_resources: 预加载的LLM资源
            skill_resources: 预加载的技能资源
            execution_context: （T6/M2 可选注入）ExecutionContext；提供时节点生命周期
                事件经 TraceService 批量缓冲落库；缺省 None 走原有行为（不接入新链路）
            
        Returns:
            执行结果
        """
        logger.info(f"开始执行智能体: agent_id={agent.id}, name={agent.name}")
        logger.debug(f"输入参数: {input_data}")

        try:
            flow_data = None
            if agent.graph_definition:
                if isinstance(agent.graph_definition, str):
                    try:
                        flow_data = json.loads(agent.graph_definition)
                    except json.JSONDecodeError:
                        logger.error("结构图字符串解析失败")
                        flow_data = None
                else:
                    flow_data = agent.graph_definition

            if flow_data and isinstance(flow_data, dict) and flow_data.get("nodes"):
                logger.info("使用 LangGraph 执行结构图")
                result = await LangGraphExecutor._execute_with_langgraph(
                    agent=agent,
                    flow_data=flow_data,
                    input_data=input_data,
                    actor=actor,
                    sse_yield_func=sse_yield_func,
                    execution_id=execution_id,
                    llm_resources=llm_resources,
                    skill_resources=skill_resources,
                    execution_context=execution_context
                )
                logger.info("=" * 50)
                logger.info("[LangGraph] ===== RETURNING =====")
                logger.info("=" * 50)
                return result
            else:
                logger.warning("没有配置流程图，使用简化执行方式")
                return await LangGraphExecutor._execute_simple(agent, input_data)
        except Exception as e:
            logger.exception(f"执行智能体失败: {str(e)}")
            import traceback
            error_result = {
                "success": False,
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            logger.info(f"[LangGraph] execute_agent 异常处理完成，准备返回错误结果")
            return error_result

    @staticmethod
    async def _preload_llm_resources(nodes: List[Dict]) -> Dict[str, Any]:
        """
        预加载所有LLM节点所需的资源（模型信息、API密钥等）
        
        Args:
            nodes: 节点列表
            
        Returns:
            预加载的资源字典，key为节点ID
            
        Raises:
            ValueError: 如果资源加载失败
        """
        from base.plugins.llm.models.model import LLMModel
        from base.plugins.llm.models.provider import LLMProvider
        from base.plugins.llm.models.api_key import LLMApiKey
        
        llm_resources = {}
        errors = []
        
        for node in nodes:
            if node.get("type") != "llm":
                continue
                
            node_id = node.get("id", "")
            node_label = node.get("data", {}).get("label", node_id)
            node_data = node.get("data", {})
            model_id = node_data.get("model_id") or node_data.get("modelId")
            
            if not model_id:
                errors.append(f"节点 [{node_label}] 未配置模型ID")
                continue
            
            logger.info(f"[预加载] 节点 [{node_label}] 的模型资源, model_id={model_id}")
            
            try:
                model = await LLMModel.get_or_none(id=model_id, status="active")
                if not model:
                    errors.append(f"节点 [{node_label}] 模型不存在或未激活: model_id={model_id}")
                    continue
                
                provider = await LLMProvider.get_or_none(id=model.provider_id)
                if not provider:
                    errors.append(f"节点 [{node_label}] 提供者不存在: provider_id={model.provider_id}")
                    continue
                
                api_key = await LLMApiKey.get_or_none(model_id=model.id)
                if not api_key:
                    errors.append(f"节点 [{node_label}] API密钥不存在: model_id={model.id}")
                    continue
                
                endpoint_url = model.endpoint_url or provider.api_endpoint
                if endpoint_url:
                    endpoint_url = endpoint_url.rstrip('/')
                    if '/responses' in endpoint_url:
                        endpoint_url = endpoint_url.split('/responses')[0]
                    if endpoint_url.endswith('/chat/completions'):
                        endpoint_url = endpoint_url[:-len('/chat/completions')]
                
                # 只存储需要的数据，而不是完整的 ORM 对象
                llm_resources[node_id] = {
                    "provider_name": provider.name_en,
                    "api_key_str": api_key.api_key,
                    "api_secret": api_key.api_secret,
                    "endpoint_url": endpoint_url,
                    "model_id_for_call": model.model_id if model.model_id else model.model_name,
                    "model_name": model.model_name,
                    "node_label": node_label
                }
                
                logger.info(f"[预加载] 节点 [{node_label}] 资源加载成功: {model.model_name}")
                
            except Exception as e:
                errors.append(f"节点 [{node_label}] 资源加载异常: {str(e)}")
                logger.exception(f"[预加载] 节点 [{node_label}] 资源加载失败: {e}")
        
        # 如果有错误，抛出异常
        if errors:
            error_msg = "LLM资源预加载失败:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"[预加载] 完成，共加载 {len(llm_resources)} 个LLM节点资源")
        return llm_resources

    @staticmethod
    async def _preload_skill_resources(nodes: List[Dict]) -> Dict[int, Any]:
        """
        预加载所有技能节点的技能信息
        
        Args:
            nodes: 节点列表
            
        Returns:
            预加载的技能字典，key为技能ID
        """
        from base.plugins.agent.models.skill import Skill
        from base.plugins.agent.services.skill_service import SkillService
        
        skill_resources = {}
        all_skill_ids = set()
        
        # 收集所有需要加载的技能ID
        for node in nodes:
            node_data = node.get("data", {})
            skill_ids = node_data.get("skill_ids", []) or node_data.get("skillIds", [])
            all_skill_ids.update(skill_ids)
        
        if not all_skill_ids:
            logger.info("[预加载] 没有需要加载的技能")
            return skill_resources
        
        logger.info(f"[预加载] 开始加载 {len(all_skill_ids)} 个技能资源...")
        
        for skill_id in all_skill_ids:
            try:
                skill = await Skill.get_or_none(id=skill_id, status="active")
                if skill:
                    bound_tools = SkillService.parse_bound_tools(skill.implementation)
                    skill_resources[skill_id] = {
                        "id": skill.id,
                        "name": skill.name,
                        "description": skill.description,
                        "implementation": skill.implementation,
                        "bound_tools": bound_tools
                    }
                    logger.info(f"[预加载] 技能加载成功: {skill.name} (ID: {skill.id})")
                else:
                    logger.warning(f"[预加载] 技能不存在或未激活: skill_id={skill_id}")
            except Exception as e:
                logger.exception(f"[预加载] 技能加载失败: skill_id={skill_id}, error={e}")
        
        logger.info(f"[预加载] 完成，共加载 {len(skill_resources)} 个技能资源")
        return skill_resources

    @staticmethod
    async def _execute_with_langgraph(
        agent: Agent,
        flow_data: Dict[str, Any],
        input_data: Dict[str, Any],
        actor: dict,
        sse_yield_func=None,
        execution_id: Optional[str] = None,
        llm_resources: Optional[Dict] = None,
        skill_resources: Optional[Dict] = None,
        execution_context=None
    ) -> Dict[str, Any]:
        """
        使用真正的 LangGraph 执行智能体结构图
        
        Args:
            agent: 智能体对象
            flow_data: 结构图数据
            input_data: 输入数据
            actor: 智能体执行上下文
            sse_yield_func: SSE推送回调函数
            execution_id: 执行ID（用于追踪）
            llm_resources: 预加载的LLM资源
            skill_resources: 预加载的技能资源
            
        Returns:
            执行结果
        """
        try:
            memory_list = []
            recent_memories = []
            important_memories = []
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", [])

            # T6/M2 可选注入：创建 Trace 写入器并发出 run_started（缺省 None 不接入新链路）
            m2_writer = None
            if execution_context is not None:
                try:
                    from base.plugins.agent.services.trace_service import TraceService
                    from base.plugins.agent.services.engine import events as m2_events
                    import time as _time
                    m2_writer = await TraceService.create_writer(
                        int(execution_context.execution_id)
                    )
                    await m2_writer.emit(
                        m2_events.EventType.RUN_STARTED, None,
                        m2_events.run_started(
                            int(execution_context.execution_id),
                            getattr(execution_context, "version_id", None), _time.time(),
                        ),
                    )
                except Exception as e:
                    logger.warning(f"[M2] Trace 写入器创建失败（不影响执行）: {e}")
                    m2_writer = None

            if not nodes:
                logger.warning("结构图没有节点，回退到简单执行")
                return await LangGraphExecutor._execute_simple(agent, input_data)

            # 使用传入的预加载资源，如果没有则执行预加载
            if llm_resources is None:
                logger.info("[预加载] 开始预加载LLM节点资源...")
                llm_resources = await LangGraphExecutor._preload_llm_resources(nodes)
                logger.info(f"[预加载] LLM资源预加载完成，资源数: {len(llm_resources)}")
            else:
                logger.info(f"[预加载] 使用传入的LLM资源，资源数: {len(llm_resources)}")

            if skill_resources is None:
                logger.info("[预加载] 开始预加载技能资源...")
                skill_resources = await LangGraphExecutor._preload_skill_resources(nodes)
                logger.info(f"[预加载] 技能资源预加载完成，资源数: {len(skill_resources)}")
            else:
                logger.info(f"[预加载] 使用传入的技能资源，资源数: {len(skill_resources)}")

            workflow = StateGraph(AgentState)
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
                    result = await LangGraphExecutor._execute_node_with_logging(
                        node, state, sse_yield_func=sse_yield_func
                    )
                    logger.debug(f"节点执行器返回状态: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                    return result
                return node_executor

            for node in nodes:
                node_id = node.get("id", "")
                node_type = node.get("type", "")
                if not node_id:
                    continue

                logger.debug(f"创建节点: {node_id} (类型: {node_type})")

                workflow.add_node(node_id, create_node_executor(node))

            edge_map = {}
            for edge in edges:
                source = edge.get("source", "")
                target = edge.get("target", "")
                if source and target:
                    edge_map[source] = target

            if start_node_id in node_map:
                logger.info(f"添加起始边: START -> {start_node_id}")
                workflow.add_edge(START, start_node_id)
            else:
                logger.error(f"开始节点 {start_node_id} 不在节点映射中")

            condition_edges = {}
            logger.info(f"边列表: {edges}")
            for edge in edges:
                source = edge.get("source", "")
                target = edge.get("target", "")
                if source and target:
                    source_node = node_map.get(source)
                    if source_node and source_node.get("type") == "condition":
                        if source not in condition_edges:
                            condition_edges[source] = []
                        condition_edges[source].append(edge)
                        logger.info(f"条件边: {source} -> {target}, 条件: {edge.get('condition', '')}, 优先级: {edge.get('priority', 0)}")
                    else:
                        logger.info(f"添加边: {source} -> {target}")
                        workflow.add_edge(source, target)

            import re
            
            for condition_node_id, edge_list in condition_edges.items():
                def create_condition_router(node_id, edges):
                    async def condition_router(state: Dict[str, Any]):
                        variables = state.get("variables", {})
                        
                        # 分离条件边和默认边
                        conditional_edges = []
                        default_edges = []
                        
                        for edge in edges:
                            condition = edge.get("condition", "").strip()
                            if condition:
                                conditional_edges.append(edge)
                            else:
                                default_edges.append(edge)
                        
                        # 按优先级排序条件边
                        conditional_edges.sort(key=lambda x: x.get("priority", 0))
                        
                        logger.info(f"条件节点 {node_id}: {len(conditional_edges)} 条条件边, {len(default_edges)} 条默认边")
                        
                        # 依次检查条件边
                        for edge in conditional_edges:
                            if not edge.get("enabled", True):
                                logger.info(f"边 {edge.get('id')} 已禁用，跳过")
                                continue
                                
                            condition = edge.get("condition", "")
                            edge_target = edge.get("target", "")
                            
                            try:
                                # 定义安全的变量获取函数
                                def get_var(data, *keys):
                                    for key in keys:
                                        if data is None or not isinstance(data, dict):
                                            return None
                                        data = data.get(key, None)
                                    return data
                                
                                # 打印 params 变量内容用于调试
                                params_value = variables.get("params", {})
                                logger.info(f"[条件判断] params 变量内容: {json.dumps(params_value, ensure_ascii=False)}")
                                logger.info(f"[条件判断] condition_result 变量内容: {json.dumps(variables.get('condition_result', {}), ensure_ascii=False)}")
                                logger.info(f"[条件判断] 原始条件表达式: {condition}")
                                
                                # 将模板语法转换为可执行表达式
                                def replace_template(match):
                                    path = match.group(1)
                                    parts = path.split('.')
                                    result = "get_var(variables"
                                    for part in parts:
                                        result += f", '{part}'"
                                    result += ")"
                                    return result
                                
                                import re
                                # 调试：检查正则匹配
                                matches = re.findall(r'\{\{(\w+(\.\w+)*)\}\}', condition)
                                logger.info(f"[条件判断] 正则匹配结果: {matches}")
                                
                                expr = re.sub(r'\{\{(\w+(\.\w+)*)\}\}', replace_template, condition)
                                logger.info(f"[条件判断] 转换后的表达式: {expr}")
                                
                                result = safe_eval(expr, {"variables": variables, "get_var": get_var})
                                
                                if result:
                                    logger.info(f"条件边匹配成功: {edge.get('id')} -> {edge_target}, 条件: {condition}")
                                    return edge_target
                            except Exception as e:
                                logger.warning(f"条件表达式执行失败 [{edge.get('id')}]: {e}, 条件: {condition}")
                        
                        # 如果没有条件匹配，处理默认边
                        if default_edges:
                            # 检查是否有多个默认边
                            if len(default_edges) > 1:
                                logger.warning(f"条件节点 {node_id} 有 {len(default_edges)} 条默认边（condition为空的边），建议每个条件节点只保留一条默认边")
                            
                            # 按优先级排序默认边
                            default_edges.sort(key=lambda x: x.get("priority", 0))
                            default_edge = default_edges[0]
                            default_target = default_edge.get("target")
                            logger.info(f"使用默认路由: {default_edge.get('id')} -> {default_target}")
                            return default_target
                        
                        logger.warning(f"条件节点 {node_id} 没有找到匹配的边，返回 END")
                        return END
                    return condition_router

                if len(edge_list) > 0:
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

            logger.info("LangGraph 编译完成")

            initial_state: Dict[str, Any] = {
                "input": input_data,
                "output": {},
                "messages": [],
                "variables": {
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "execution_id": execution_id,
                    "recent_memories": memory_list,
                    "important_memories": [{"content": m.content, "importance": m.importance} for m in important_memories],
                    "_llm_resources": llm_resources,  # 预加载的LLM资源
                    "_skill_resources": skill_resources,  # 预加载的技能资源
                    "_m2_trace_writer": m2_writer  # T6/M2 可选注入的 Trace 写入器（不向前端暴露）
                },
                "node_results": {},
                "execution_trace": [],
                "current_node": None,
                "error": None,
                "flow_data": flow_data  # 新增：将图结构存入状态，供并行节点使用
            }

            logger.info("使用 LangGraph 执行")
            logger.debug(f"初始状态: {json.dumps(initial_state, ensure_ascii=False, default=str)[:500]}...")
            checkpoint_service = CheckpointService.get_instance()
            checkpointer = checkpoint_service.get_checkpointer()
            config = checkpoint_service.build_config(
                actor=actor,
                agent_id=agent.id,
                agent_name=agent.name,
                execution_id=execution_id
            )
            logger.info(f"[编译图] 配置: {json.dumps(config, ensure_ascii=False)}")
            logger.info(f"[编译图] execution_id: {execution_id}")

            graph_with_memory = workflow.compile(checkpointer=checkpointer)
            
            # import uuid
            # thread_id = str(uuid.uuid4())
            # config = {"configurable": {"thread_id": thread_id}}
            # logger.debug(f"配置: {json.dumps(config, ensure_ascii=False)}")

            logger.info("调用 graph.ainvoke...")
            start_time = time.time()
            try:
                current_state = await graph_with_memory.aget_state(config)
                is_paused = current_state and current_state.values.get("__interrupt__") is not None
            except Exception as e:
                logger.warning(f"获取当前状态失败: {e}")
                current_state = None
                is_paused = False
            
            if is_paused:
                # ✅ 恢复暂停：用户输入
                user_input = input_data.get("text", "")
                logger.info(f"[恢复执行] 从暂停点继续，用户输入: {user_input}")
                final_state = await graph_with_memory.ainvoke(
                    Command(resume=user_input),
                    config=config
                )
            elif current_state and current_state.values:
                # ✅ 继续对话：合并新输入到已有状态（保留历史消息和参数）
                logger.info(f"[继续对话] 从检查点恢复状态并合并新输入")
                merged_state = {**current_state.values, "input": input_data}
                final_state = await graph_with_memory.ainvoke(merged_state, config)
            else:
                # ✅ 首次执行
                logger.info(f"[首次执行] 初始状态: {json.dumps(initial_state, ensure_ascii=False, default=str)[:500]}...")
                final_state = await graph_with_memory.ainvoke(initial_state, config)

            elapsed = time.time() - start_time
            logger.info(f"LangGraph 执行完成，耗时: {elapsed:.2f}秒")
            logger.debug(f"最终状态: {json.dumps(final_state, ensure_ascii=False, default=str)[:500]}...")

            await LangGraphExecutor._save_result_to_memory(
                agent=agent,
                state=final_state,
                input_data=input_data,
                actor=actor
            )
            logger.info("[LangGraph] 记忆保存完成，准备返回结果")

            if final_state.get("error"):
                # T6/M2：run_failed 事件（节点错误已传导至 state.error）
                if m2_writer is not None:
                    try:
                        await m2_writer.emit(
                            m2_events.EventType.RUN_FAILED, None,
                            m2_events.run_failed(
                                int(execution_context.execution_id), "NODE_ERROR",
                                message=str(final_state.get("error", ""))[:500],
                            ),
                        )
                    except Exception as emit_err:
                        logger.warning(f"[M2] run_failed 事件写入失败（不影响执行）: {emit_err}")
                return {
                    "success": False,
                    "message": final_state["error"],
                    "input": input_data,
                    "output": final_state.get("output", {}),
                    "variables": final_state.get("variables", {}),
                    "trace": final_state.get("execution_trace", [])
                }
            logger.info("[LangGraph] 下一步返回结果")
            logger.info("[LangGraph] 准备返回执行结果")
            
            output = final_state.get("output", {})
            variables = final_state.get("variables", {})
            
            logger.info(f"[LangGraph] 最终状态 - output: {json.dumps(output, ensure_ascii=False)}")
            logger.info(f"[LangGraph] 最终状态 - variables.keys: {list(variables.keys())}")
            
            if "llm_output" in variables:
                llm_output = variables["llm_output"]
                logger.info(f"[LangGraph] llm_output 内容: {json.dumps(llm_output, ensure_ascii=False)[:500]}...")
            
            # 查找输出节点设置的内容
            extracted_text = ""
            for key in list(output.keys()):
                if key != "end_time":
                    value = output[key]
                    if isinstance(value, dict):
                        if "text" in value:
                            extracted_text = value["text"]
                            output["text"] = extracted_text
                            logger.info(f"[LangGraph] 已从 output.{key}.text 提取内容")
                            break
                        elif "response" in value:
                            extracted_text = value["response"]
                            output["text"] = extracted_text
                            logger.info(f"[LangGraph] 已从 output.{key}.response 提取内容")
                            break
            
            # 如果没有从 output 中提取到内容，尝试从 variables 中获取
            if not extracted_text:
                llm_output = variables.get("llm_output", variables.get("llmOutput", {}))
                if isinstance(llm_output, dict):
                    extracted_text = llm_output.get("response", llm_output.get("text", ""))
                elif isinstance(llm_output, str):
                    extracted_text = llm_output
                
                if extracted_text:
                    output["text"] = extracted_text
                    logger.info(f"[LangGraph] 已从 variables.llm_output 提取内容")
            
            # 如果仍然没有内容，尝试其他常见变量
            if not extracted_text:
                for var_name in ["finalReport", "final_report", "result", "response"]:
                    if var_name in variables:
                        value = variables[var_name]
                        if isinstance(value, dict):
                            extracted_text = value.get("text", value.get("response", str(value)))
                        else:
                            extracted_text = str(value)
                        if extracted_text:
                            output["text"] = extracted_text
                            logger.info(f"[LangGraph] 已从 variables.{var_name} 提取内容")
                            break
            
            # 过滤敏感数据，不向前端暴露 API 密钥等敏感信息
            safe_variables = variables.copy()
            sensitive_keys = ["_llm_resources", "_skill_resources", "_m2_trace_writer"]
            for key in sensitive_keys:
                if key in safe_variables:
                    del safe_variables[key]
            
            # T6/M2：run_completed 事件
            if m2_writer is not None:
                try:
                    await m2_writer.emit(
                        m2_events.EventType.RUN_COMPLETED, None,
                        m2_events.run_completed(
                            int(execution_context.execution_id), {}, int(elapsed * 1000),
                        ),
                    )
                except Exception as emit_err:
                    logger.warning(f"[M2] run_completed 事件写入失败（不影响执行）: {emit_err}")
            result = {
                "success": True,
                "message": "执行成功",
                "input": input_data,
                "output": output,
                "variables": safe_variables,
                "trace": final_state.get("execution_trace", [])
            }
            logger.info(f"[LangGraph] 返回结果: success={result['success']}, output_keys={list(result['output'].keys())}")
            return result

        except GraphInterrupt as e:
            logger.info(f"[LangGraph] 执行暂停，等待用户输入: {e}")
            # T6/M2：run_paused 事件（HITL 等待用户输入）
            if m2_writer is not None:
                try:
                    await m2_writer.emit(
                        m2_events.EventType.RUN_PAUSED, None,
                        m2_events.run_paused("", {"type": "user"}, None),
                    )
                except Exception as emit_err:
                    logger.warning(f"[M2] run_paused 事件写入失败（不影响执行）: {emit_err}")
            return {
                "success": True,
                "status": "waiting_for_user",
                "execution_id": execution_id,
                "message": "等待用户输入"
            }
        except Exception as e:
            logger.exception(f"LangGraph 执行失败: {e}")
            # T6/M2：run_failed 事件
            if m2_writer is not None:
                try:
                    await m2_writer.emit(
                        m2_events.EventType.RUN_FAILED, None,
                        m2_events.run_failed(
                            int(execution_context.execution_id), "ENGINE_ERROR",
                            message=str(e)[:500],
                        ),
                    )
                except Exception as emit_err:
                    logger.warning(f"[M2] run_failed 事件写入失败（不影响执行）: {emit_err}")
            import traceback
            return {
                "success": False,
                "message": str(e),
                "traceback": traceback.format_exc()
            }
        finally:
            # T6/M2：关闭 Trace 写入器（终 flush，R-11）
            if m2_writer is not None:
                try:
                    from base.plugins.agent.services.trace_service import TraceService
                    await TraceService.close_writer(m2_writer.execution_id)
                except Exception as close_err:
                    logger.warning(f"[M2] Trace 写入器关闭失败: {close_err}")

    @staticmethod
    async def _execute_node_with_logging(current_node, state, sse_yield_func=None):
        """执行节点，带日志记录和 SSE 推送"""
        node_id = current_node.get("id", "")
        node_type = current_node.get("type")
        node_data = current_node.get("data", {})
        node_label = node_data.get("label", node_type)

        logger.info(f"执行节点 [{node_id}]: {node_type}")
        
        # 保存原始 flow_data，确保在状态传递过程中不会丢失
        original_flow_data = state.get("flow_data")

        state["current_node"] = node_label

        # T6/M2：node_started 事件（可选注入，缺省 None 不接入新链路）
        m2_writer = (state.get("variables") or {}).get("_m2_trace_writer")
        m2_node_start = time.time()
        if m2_writer is not None:
            try:
                from base.plugins.agent.services.engine import events as m2_events
                await m2_writer.emit(
                    m2_events.EventType.NODE_STARTED, node_id,
                    m2_events.node_started(node_id, node_label),
                )
            except Exception as emit_err:
                logger.warning(f"[M2] node_started 事件写入失败（不影响执行）: {emit_err}")

        if "execution_trace" not in state:
            state["execution_trace"] = []
        step_count = len(state["execution_trace"]) + 1

        if sse_yield_func:
            try:
                logger.debug(f"准备发送节点开始事件: {node_id}")
                await sse_yield_func({
                    'type': 'node_start',
                    'node_id': node_id,
                    'node_type': node_type,
                    'node_label': node_label,
                    'step': step_count
                })
                logger.debug(f"节点开始事件发送成功: {node_id}")
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
                state = await LangGraphExecutor._execute_input_node(node_data, state)
            elif node_type == "output":
                state = await LangGraphExecutor._execute_output_node(node_data, state)
            elif node_type == "agent":
                state = await LangGraphExecutor._execute_agent_node(node_data, state)
            elif node_type == "llm":
                node_data = current_node.get("data", {})
                stream_val = node_data.get("stream", False)
                # 支持布尔值 True/False 和字符串 "true"/"false"
                is_streaming = stream_val is True or (isinstance(stream_val, str) and stream_val.lower() == 'true')
                if sse_yield_func:
                    await sse_yield_func({'type': 'thinking', 'label': node_label, 'message': '正在调用大模型...'})
                if is_streaming and sse_yield_func:
                    state = await LangGraphExecutor._execute_llm_node_streaming(
                        current_node,
                        state,
                        sse_yield_func=sse_yield_func
                    )
                else:
                    state = await LangGraphExecutor._execute_llm_node(current_node, state)
            elif node_type == "skill":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': f'执行技能: {node_data.get("skill_id", "unknown")}'})
                state = await LangGraphExecutor._execute_skill_node(node_data, state)
            elif node_type == "tool":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': f'执行工具: {node_data.get("tool_name", "unknown")}'})
                state = await LangGraphExecutor._execute_tool_node(node_data, state)
            elif node_type == "condition":
                if sse_yield_func:
                    await sse_yield_func({'type': 'thinking', 'label': node_label, 'message': '条件判断中...'})
                state = await LangGraphExecutor._execute_condition_node(node_data, state)
                if sse_yield_func:
                    condition_result = state.get("variables", {}).get("condition_result", {}).get("result", False)
                    await sse_yield_func({'type': 'observation', 'label': '条件判断结果', 'content': f'结果: {condition_result}'})
            elif node_type == "loop":
                state = await LangGraphExecutor._execute_loop_node(node_data, state)
            elif node_type == "iteration":
                state = await LangGraphExecutor._execute_iteration_node(node_data, state)
            elif node_type == "parallel":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': '并行执行分支任务...'})
                state = await LangGraphExecutor._execute_parallel_node(current_node, state)
            elif node_type == "http":
                if sse_yield_func:
                    await sse_yield_func({'type': 'action', 'label': node_label, 'message': '发送HTTP请求'})
                logger.info(f"http节点类型: {node_type}")
                state = await LangGraphExecutor._execute_http_node(node_data, state)
            elif node_type == "code":
                state = await LangGraphExecutor._execute_code_node(node_data, state)
            elif node_type == "template":
                state = await LangGraphExecutor._execute_template_node(node_data, state)
            elif node_type == "variable_aggregator":
                state = await LangGraphExecutor._execute_variable_aggregator_node(node_data, state)
            elif node_type == "document_extractor":
                state = await LangGraphExecutor._execute_document_extractor_node(node_data, state)
            elif node_type == "variable_assigner":
                state = await LangGraphExecutor._execute_variable_assigner_node(node_data, state)
            elif node_type == "parameter_extractor":
                state = await LangGraphExecutor._execute_parameter_extractor_node(node_data, state)
            elif node_type == "json_extractor":
                state = await LangGraphExecutor._execute_json_extractor_node(node_data, state)
            else:
                state = await LangGraphExecutor._execute_default_node(node_data, state)

            state["execution_trace"].append({
                "node_id": node_id,
                "node_type": node_type,
                "label": node_label,
                "timestamp": datetime.now().isoformat()
            })

            # T6/M2：node_completed 事件
            if m2_writer is not None:
                try:
                    ms = int((time.time() - m2_node_start) * 1000)
                    await m2_writer.emit(
                        m2_events.EventType.NODE_COMPLETED, node_id,
                        m2_events.node_completed(node_id, None, ms),
                    )
                except Exception as emit_err:
                    logger.warning(f"[M2] node_completed 事件写入失败（不影响执行）: {emit_err}")

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
            # T6/M2：node_failed 事件
            if m2_writer is not None:
                try:
                    await m2_writer.emit(
                        m2_events.EventType.NODE_FAILED, node_id,
                        m2_events.node_failed(node_id, "NODE_ERROR", False, str(e)[:500]),
                    )
                except Exception as emit_err:
                    logger.warning(f"[M2] node_failed 事件写入失败（不影响执行）: {emit_err}")
            if sse_yield_func:
                await sse_yield_func({'type': 'error', 'node_id': node_id, 'message': str(e)})

        # 确保 flow_data 在状态传递过程中不会丢失
        if original_flow_data is not None and "flow_data" not in state:
            state["flow_data"] = original_flow_data

        return state

    @staticmethod
    async def _execute_simple(agent: Agent, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """简化的执行方式"""
        logger.info("使用简化执行方式")

        try:
            input_text = input_data.get("text", "")

            return {
                "success": True,
                "message": "执行成功",
                "input": input_data,
                "output": {
                    "text": f"已处理: {input_text}"
                }
            }

        except Exception as e:
            logger.exception(f"简化执行失败: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    @staticmethod
    def _find_start_node(nodes: List[Dict]) -> Optional[Dict]:
        """找到开始节点"""
        for node in nodes:
            if node.get("type") == "start":
                return node

        if nodes:
            return nodes[0]
        return None

    @staticmethod
    async def _execute_start_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行开始节点"""
        state["variables"]["start_time"] = datetime.now().isoformat()
        return state

    @staticmethod
    async def _save_result_to_memory(agent, state, input_data, actor=None):
        """保存执行结果到长期记忆"""
        try:
            from base.plugins.agent.schemas.memory import MemoryCreate

            variables = state.get("variables", {}) if isinstance(state, dict) else {}

            memory_mode = getattr(agent, "default_memory_mode", "public")

            input_text = input_data.get("text", "")
            if input_text:
                input_memory_data = MemoryCreate(
                    agent_id=agent.id,
                    content=f"用户输入: {input_text}",
                    type="short_term",
                    importance=0.8,
                    memory_mode=memory_mode,
                    customer_id=actor.get('id')if memory_mode == "private" and actor.get('type') =='cus' else None,
                    user_id=actor.get('id') if memory_mode == "private" and actor.get('type') =='usr' else None
                )
                await MemoryService.create_memory(input_memory_data)
                logger.info("保存记忆: 输入内容已保存")

            key_variables = ["wbs_result", "task_plan", "task_decomposition", "thinking_result",
                             "final_output", "output", "structured_output"]

            logger.info(f"[保存记忆] 开始检查变量: {list(variables.keys())}")
            
            for var_name in key_variables:
                if var_name in variables:
                    logger.info(f"[保存记忆] 处理变量: {var_name}")
                    value = variables[var_name]

                    content_str = ""
                    if isinstance(value, dict):
                        content_str = json.dumps(value, ensure_ascii=False)
                    elif isinstance(value, list):
                        content_str = json.dumps(value, ensure_ascii=False)
                    else:
                        content_str = str(value)

                    logger.info(f"[保存记忆] 变量 {var_name} 内容长度: {len(content_str)}")

                    if content_str and len(content_str.strip()) > 0:
                        try:
                            importance = 0.9 if var_name in ["final_output", "wbs_result", "task_plan"] else 0.7
                            memory_data = MemoryCreate(
                                agent_id=agent.id,
                                content=f"{var_name}: {content_str}",
                                type="long_term",
                                importance=importance,
                                memory_mode=memory_mode,
                                customer_id=actor.get('id')if memory_mode == "private" and actor.get('type') =='cus' else None,
                                user_id=actor.get('id') if memory_mode == "private" and actor.get('type') =='usr' else None
                            )
                            logger.info(f"[保存记忆] 准备保存 {var_name}")
                            await MemoryService.create_memory(memory_data)
                            logger.info(f"保存记忆: {var_name} 已保存")
                        except Exception as e:
                            logger.warning(f"保存记忆失败: {e}")
                else:
                    logger.debug(f"[保存记忆] 变量 {var_name} 不存在")

        except Exception as e:
            logger.warning(f"保存记忆时出错: {e}")

    @staticmethod
    async def _execute_end_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行结束节点"""
        state["output"]["end_time"] = datetime.now().isoformat()
        return state

    @staticmethod
    async def _execute_input_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行输入节点 - 自动保存检查点并暂停，等待用户输入
        恢复后会把用户输入写入 variables["user_input"]
        """
        # 暂停在这里，自动 checkpoint，等待外部 Command(resume=xxx)
        interrupt("等待用户输入")
        # 注意：interrupt() 会抛出异常暂停执行，下面的代码在恢复后执行
        
        # 恢复执行后，检查是否有用户输入
        user_input = state.get("input", {}).get("text", "")
        if user_input:
            state["variables"]["user_input"] = user_input
            state["variables"]["user_input_received"] = True
            logger.info(f"[input节点] 收到用户输入: {user_input}")
        
        return state

    @staticmethod
    async def _execute_output_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行输出节点"""
        output_var = node_data.get("outputVar", "result")
        output_content = node_data.get("outputContent", "")

        variables = state.get("variables", {})

        # 调试日志
        logger.info(f"[输出节点] 开始执行")
        logger.info(f"[输出节点] outputVar: {output_var}")
        logger.info(f"[输出节点] output_content: {output_content}")
        logger.info(f"[输出节点] 可用变量: {list(variables.keys())}")
        
        # 打印关键变量内容
        if "params" in variables:
            logger.info(f"[输出节点] params 变量内容: {json.dumps(variables['params'], ensure_ascii=False)}")
        if "final_report" in variables:
            logger.info(f"[输出节点] final_report 变量内容: {variables['final_report']}")
        if "llm_output" in variables:
            logger.info(f"[输出节点] llm_output 变量内容: {json.dumps(variables['llm_output'], ensure_ascii=False)}")

        if output_content:
            logger.info(f"[输出节点] 使用自定义输出内容模板")
            import re
            
            def replace_var(match):
                path = match.group(1)
                parts = path.split('.')
                value = variables
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = ""
                        break
                
                # 如果值为 None，返回空字符串
                if value is None:
                    return ""
                
                return str(value)
            
            output_content = re.sub(r'\{\{(\w+(\.\w+)*)\}\}', replace_var, output_content)
            state["output"][output_var] = {"text": output_content}
            logger.info(f"[输出节点] 输出结果: {output_content}")
        else:
            # 检查是否有最终报告变量
            final_report = variables.get("finalReport", variables.get("final_report", ""))
            if final_report:
                logger.info(f"[输出节点] 使用 finalReport/final_report 变量")
                state["output"][output_var] = {"text": final_report}
                logger.info(f"[输出节点] 输出结果: {final_report}")
            else:
                # 尝试获取LLM输出
                llm_output = variables.get("llm_output", variables.get("llmOutput", {}))
                if isinstance(llm_output, dict):
                    llm_text = llm_output.get("response", llm_output.get("text", ""))
                    if llm_text:
                        logger.info(f"[输出节点] 使用 llm_output.response/text")
                        state["output"][output_var] = {"text": llm_text}
                        logger.info(f"[输出节点] 输出结果: {llm_text[:100]}...")
                    else:
                        logger.info(f"[输出节点] llm_output 中没有 response/text，使用所有变量")
                        state["output"][output_var] = {"text": str(variables)}
                        logger.info(f"[输出节点] 输出结果: {str(variables)[:100]}...")
                else:
                    logger.info(f"[输出节点] llm_output 不是字典，使用所有变量")
                    state["output"][output_var] = {"text": str(variables)}
                    logger.info(f"[输出节点] 输出结果: {str(variables)[:100]}...")

        logger.info(f"[输出节点] state['output']: {json.dumps(state.get('output', {}), ensure_ascii=False)}")
        return state

    @staticmethod
    async def _execute_agent_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行智能体节点"""
        variables = state.get("variables", {})
        state["variables"]["agent_info"] = {
            "id": variables.get("agent_id"),
            "name": variables.get("agent_name"),
            "description": ""
        }
        return state

    @staticmethod
    async def _get_skills_and_tools(skill_ids: List[int], prompt: str, state: Dict[str, Any] = None) -> tuple:
        """获取技能数据和绑定的工具（优先使用预加载资源）"""
        skills_data = []
        bound_tools_set = set()
        
        if skill_ids:
            # 优先使用预加载的技能资源
            skill_resources = {}
            if state:
                skill_resources = state.get("variables", {}).get("_skill_resources", {})
            
            for skill_id in skill_ids:
                skill_data = skill_resources.get(skill_id)
                
                if skill_data:
                    # 使用预加载资源
                    logger.info(f"[技能资源] 使用预加载资源: skill_id={skill_id}, name={skill_data['name']}")
                    skills_data.append({
                        "id": skill_data["id"],
                        "name": skill_data["name"],
                        "description": skill_data["description"],
                        "implementation": skill_data["implementation"]
                    })
                    if skill_data.get("bound_tools"):
                        for tool in skill_data["bound_tools"]:
                            bound_tools_set.add(tool)
                else:
                    # 回退到数据库查询
                    logger.info(f"[技能资源] 预加载资源不可用，回退到数据库查询: skill_id={skill_id}")
                    try:
                        from base.plugins.agent.models.skill import Skill
                        from base.plugins.agent.services.skill_service import SkillService
                        
                        skill = await Skill.get_or_none(id=skill_id, status="active")
                        if skill:
                            logger.debug(f"找到技能: {skill.name} (ID: {skill.id})")
                            skills_data.append({
                                "id": skill.id,
                                "name": skill.name,
                                "description": skill.description,
                                "implementation": skill.implementation
                            })
                            bound_tools = SkillService.parse_bound_tools(skill.implementation)
                            if bound_tools:
                                for tool in bound_tools:
                                    bound_tools_set.add(tool)
                        else:
                            logger.warning(f"技能不存在或未激活: skill_id={skill_id}")
                    except Exception as e:
                        logger.exception(f"获取技能信息失败: {e}")

        if skills_data:
            skill_context = "\n【可用技能】:\n"
            for skill in skills_data:
                skill_context += f"技能名称: {skill['name']}\n"
                skill_context += f"技能描述: {skill['description']}\n"
                skill_context += f"技能实现: {skill['implementation']}\n\n"

            if prompt:
                prompt = skill_context + "\n" + prompt
            else:
                prompt = skill_context

        tools = []
        functions = []
        if bound_tools_set:
            try:
                from base.plugins.agent.tools.registry import ToolRegistry
                all_tools_info = ToolRegistry.get_all_tools_info()
                for tool_name in bound_tools_set:
                    if tool_name in all_tools_info:
                        tools.append(all_tools_info[tool_name])
                        functions.append(all_tools_info[tool_name])
                    else:
                        logger.warning(f"工具未注册: {tool_name}")
                logger.info(f"获取到 {len(tools)} 个可用工具（{len(bound_tools_set) - len(tools)} 个未注册）")
            except Exception as e:
                logger.exception(f"获取工具信息失败: {e}")

        return prompt, tools, functions

    @staticmethod
    async def _build_chat_kwargs(
        node_data: Dict,
        actual_model_for_call: str,
        messages: List[Dict],
        functions: List = None
    ) -> Dict[str, Any]:
        """构建聊天参数，从节点配置中读取 temperature 和 max_tokens"""
        temperature = node_data.get("temperature")
        if temperature is None:
            temperature = 0.7

        max_tokens = node_data.get("max_tokens")
        if max_tokens is None or max_tokens == 0 or max_tokens == "":
            max_tokens = None

        chat_kwargs = {
            "model": actual_model_for_call,
            "messages": messages,
            "temperature": temperature
        }

        if max_tokens is not None:
            chat_kwargs["max_tokens"] = max_tokens

        if functions:
            chat_kwargs["functions"] = functions
            chat_kwargs["function_call"] = "auto"

        return chat_kwargs

    @staticmethod
    async def _build_messages(prompt: str, node_data: Dict, state: Dict[str, Any]) -> tuple:
        """构建消息列表（包含变量替换、记忆上下文）"""
        variables = state.get("variables", {})
        for key, value in variables.items():
            prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

        # 优先从 state["input"] 获取输入数据，其次从 variables["input"] 获取
        input_data = state.get("input", {})
        if isinstance(input_data, dict):
            input_text = input_data.get("text", "")
        elif isinstance(input_data, str):
            input_text = input_data
        else:
            input_text = variables.get("input", {}).get("text", "")
        system_prompt = node_data.get("system_prompt", "")

        messages = [{"role": "system", "content": system_prompt}]

        # 添加之前的对话历史
        existing_messages = state.get("messages", [])
        if existing_messages:
            messages.extend(existing_messages)

        recent_memories = variables.get("recent_memories", [])
        important_memories = variables.get("important_memories", [])

        if recent_memories or important_memories:
            memory_context = "\n"
            if important_memories:
                memory_context += "【重要历史记忆】:\n"
                for idx, m in enumerate(important_memories):
                    memory_content = m.get("content", m) if isinstance(m, dict) else str(m)
                    memory_context += f"{idx+1}. {memory_content}\n"
                memory_context += "\n"
            if recent_memories:
                memory_context += "【最近记忆】:\n"
                for idx, m in enumerate(recent_memories):
                    memory_content = m.get("content", m) if isinstance(m, dict) else str(m)
                    memory_context += f"{idx+1}. {memory_content}\n"

            if memory_context.strip():
                messages.append({"role": "user", "content": f"历史记忆和上下文信息：\n{memory_context}\n"})

        # 如果已有提取的参数，将其添加到提示词中
        # 支持多种可能的参数存储变量名
        param_variables = ["params", "llm_output", "output", "result"]
        params = {}
        
        # 从 variables 中读取参数
        for var_name in param_variables:
            var_value = variables.get(var_name, {})
            if isinstance(var_value, dict) and var_value:
                params.update(var_value)
        
        # 从对话历史中提取之前的参数（处理 JSON 格式的响应）
        existing_messages = state.get("messages", [])
        for msg in existing_messages:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if content:
                    try:
                        # 尝试解析 JSON
                        json_start = content.find("{")
                        json_end = content.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = content[json_start:json_end]
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict):
                                params.update(parsed)
                                logger.info(f"[构建消息] 从对话历史中提取参数: {list(parsed.keys())}")
                    except:
                        pass  # 不是有效的 JSON，跳过
        
        if params:
            params_str = "\n【已有参数】:\n"
            for key, value in params.items():
                if value and key not in ["prompt", "model", "response"]:  # 只显示非空参数，排除内部字段
                    params_str += f"- {key}: {value}\n"
            
            prompt = params_str + "\n" + prompt
            logger.info(f"[构建消息] 合并已有参数后的提示词: {prompt[:200]}...")

        if prompt and input_text:
            combined_content = prompt.replace("{{input}}", input_text) if "{{input}}" in prompt else f"{prompt}\n\n用户输入：{input_text}"
            messages.append({"role": "user", "content": combined_content})
        elif prompt:
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": input_text})
        logger.info(f"[构建消息] 最终消息列表: {messages}")
        
        return prompt, messages, input_text

    @staticmethod
    async def _parse_and_set_response(llm_response: str, node_data: Dict, state: Dict[str, Any], actual_model: str, prompt: str) -> Dict[str, Any]:
        """解析响应并设置变量"""
        parsed_response = None
        if llm_response:
            try:
                json_start = llm_response.find("{")
                json_end = llm_response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = llm_response[json_start:json_end]
                    parsed_response = json.loads(json_str)
                    logger.debug(f"成功解析 LLM 输出 JSON: {parsed_response}")
            except Exception as e:
                logger.warning(f"解析 JSON 失败: {e}")

        output_variable = node_data.get("outputVar", "llm_output")
        if parsed_response:
            state["variables"][output_variable] = parsed_response
            
            # 将解析出的参数合并到节点指定的输出变量中（支持持久化）
            # 如果 outputVar 不是默认的 llm_output，则直接使用它作为持久化变量
            persist_var = output_variable if output_variable != "llm_output" else "params"
            
            if persist_var not in state["variables"]:
                state["variables"][persist_var] = {}
            state["variables"][persist_var].update(parsed_response)
            logger.info(f"[参数合并] 更新后的 {persist_var}: {json.dumps(state['variables'][persist_var], ensure_ascii=False)}")
        else:
            state["variables"][output_variable] = {
                "prompt": prompt,
                "model": actual_model,
                "response": llm_response
            }

        # 保存对话历史到状态中，以便后续节点使用
        if "messages" not in state:
            state["messages"] = []
        
        # 获取当前输入文本
        input_data = state.get("input", {})
        if isinstance(input_data, dict):
            input_text = input_data.get("text", "")
        elif isinstance(input_data, str):
            input_text = input_data
        else:
            input_text = state.get("variables", {}).get("input", {}).get("text", "")
        
        logger.info(f"[构建消息] 大模型响应后的输入文本: {input_text}")
        
        # 添加用户输入到对话历史（如果有输入）
        if input_text:
            state["messages"].append({"role": "user", "content": input_text})
        
        # 添加AI响应到对话历史
        state["messages"].append({"role": "assistant", "content": llm_response})
        logger.info(f"[构建消息] 大模型响应后的消息列表: {state['messages']}")
        
        return state

    @staticmethod
    async def _get_llm_resource(node_id: str, state: Dict[str, Any]) -> tuple:
        """
        获取LLM资源（使用预加载的资源）
        
        Args:
            node_id: 节点ID
            state: 当前状态
            
        Returns:
            (service, model_id_for_call, error)
        """
        from base.plugins.llm.services.chat_service import ChatService
        
        llm_resources = state.get("variables", {}).get("_llm_resources", {})
        resource = llm_resources.get(node_id)
        
        if not resource:
            return None, None, f"节点资源未预加载: node_id={node_id}"
        
        node_label = resource.get("node_label", node_id)
        logger.info(f"[LLM资源] 使用预加载资源: 节点 [{node_label}], model={resource['model_name']}")
        
        try:
            service = await ChatService.get_provider_service(
                provider_name_en=resource["provider_name"],
                api_key=resource["api_key_str"],
                endpoint_url=resource["endpoint_url"],
                api_secret=resource["api_secret"]
            )
            if service:
                return service, resource["model_id_for_call"], None
            return None, None, f"节点 [{node_label}] 创建聊天服务失败"
        except Exception as e:
            logger.exception(f"[LLM资源] 创建服务失败: {e}")
            return None, None, f"节点 [{node_label}] 创建服务异常: {str(e)}"

    @staticmethod
    async def _execute_llm_node(current_node: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行LLM节点（非流式）"""
        node_id = current_node.get("id", "")
        node_data = current_node.get("data", {})
        prompt = node_data.get("prompt", "")
        model_id = node_data.get("model_id") or node_data.get("modelId")
        model_name = node_data.get("model", "gpt-3.5-turbo")
        node_label = node_data.get("label", "")
        skill_ids = node_data.get("skill_ids", []) or node_data.get("skillIds", [])

        prompt, tools, functions = await LangGraphExecutor._get_skills_and_tools(skill_ids, prompt, state)
        prompt, messages, input_text = await LangGraphExecutor._build_messages(prompt, node_data, state)
        
        # 使用预加载的资源
        service, actual_model_for_call, error = await LangGraphExecutor._get_llm_resource(node_id, state)
        actual_model = actual_model_for_call or model_name

        llm_response = ""
        try:
            if not service:
                error_msg = f"无法创建聊天服务。错误: {error}"
                logger.error(error_msg)
                state["error"] = error_msg
                llm_response = f"错误：{error_msg}"
            else:
                chat_kwargs = await LangGraphExecutor._build_chat_kwargs(
                    node_data,
                    actual_model_for_call,
                    messages,
                    functions
                )

                llm_response = await LangGraphExecutor._call_llm_with_tool_handler(service, chat_kwargs, messages)
        except Exception as e:
            logger.exception(f"调用大模型失败: {e}")
            llm_response = f"错误：调用大模型失败: {str(e)}"

        if not llm_response:
            logger.warning("使用模拟响应")
            llm_response = await LangGraphExecutor._generate_mock_response(input_text, prompt, node_label)

        state = await LangGraphExecutor._parse_and_set_response(llm_response, node_data, state, actual_model, prompt)
        return state

    @staticmethod
    async def _call_llm_with_tool_handler(service, chat_kwargs: Dict, messages: List[Dict]) -> str:
        """调用LLM并处理工具调用"""
        from base.plugins.agent.tools.registry import ToolRegistry

        try:
            logger.info(f"调用大模型: {chat_kwargs}")
            logger.info(f"messages: {messages}")
            response = await service.chat(**chat_kwargs)
            logger.info(f"大模型响应: {response}")
        except Exception as e:
            logger.exception(f"LLM调用异常: {e}")
            return f"错误：大模型调用失败: {str(e)}"

        if isinstance(response, dict) and response.get("choices"):
            message = response["choices"][0].get("message", {})

            if message.get("function_call"):
                function_call = message.get("function_call")
                function_name = function_call.get("name")
                function_args = function_call.get("arguments", {})

                logger.info(f"大模型请求调用工具: {function_name}")

                try:
                    tool_class = ToolRegistry.get_tool(function_name)
                    if tool_class:
                        tool_result = await tool_class.execute(**function_args)
                        logger.info(f"工具执行成功: {function_name}")

                        messages.append(message)
                        messages.append({
                            "role": "function",
                            "name": function_name,
                            "content": str(tool_result)
                        })

                        second_response = await service.chat(**chat_kwargs)
                        
                        if isinstance(second_response, dict) and second_response.get("choices"):
                            return second_response["choices"][0].get("message", {}).get("content", "")
                        else:
                            return str(second_response)
                    else:
                        return f"工具 {function_name} 未找到"
                except Exception as tool_e:
                    logger.exception(f"工具执行失败: {tool_e}")
                    return f"工具执行失败: {str(tool_e)}"
            else:
                return message.get("content", "")
        else:
            return str(response)

    @staticmethod
    async def _execute_llm_node_streaming(
        current_node: Dict,
        state: Dict[str, Any],
        sse_yield_func=None
    ) -> Dict[str, Any]:
        """执行LLM节点（流式）"""
        node_id = current_node.get("id", "")
        node_data = current_node.get("data", {})
        prompt = node_data.get("prompt", "")
        model_id = node_data.get("model_id") or node_data.get("modelId")
        model_name = node_data.get("model", "gpt-3.5-turbo")
        node_label = node_data.get("label", "")
        skill_ids = node_data.get("skill_ids", []) or node_data.get("skillIds", [])

        prompt, tools, functions = await LangGraphExecutor._get_skills_and_tools(skill_ids, prompt, state)
        prompt, messages, input_text = await LangGraphExecutor._build_messages(prompt, node_data, state)
        
        # 使用预加载的资源
        service, actual_model_for_call, error = await LangGraphExecutor._get_llm_resource(node_id, state)
        actual_model = actual_model_for_call or model_name

        llm_response = ""
        try:
            # logger.info(f"[LLM流式] 开始执行，node_id={node_id}, node_label={node_label}")
            
            if not service:
                error_msg = f"无法创建聊天服务。错误: {error}"
                logger.error(error_msg)
                state["error"] = error_msg
                llm_response = f"错误：{error_msg}"
            else:
                logger.info(f"[LLM流式] 聊天服务创建成功，使用模型: {actual_model_for_call}")
                
                chat_kwargs = await LangGraphExecutor._build_chat_kwargs(
                    node_data,
                    actual_model_for_call,
                    messages
                )
                # logger.info(f"[LLM流式] 构建聊天参数完成")
                
                full_response = ""
                chunk_count = 0
                # logger.info(f"[LLM流式] 开始调用 chat_stream...")
                
                try:
                    async for chunk in service.chat_stream(**chat_kwargs):
                        chunk_count += 1
                        # logger.info(f"[LLM流式] 收到第 {chunk_count} 个响应块")
                        
                        if isinstance(chunk, dict) and chunk.get("choices"):
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            full_response += content
                            # logger.info(f"[LLM流式] 提取内容: {content[:50]}...")
                            
                            if content and sse_yield_func:
                                # logger.info(f"[LLM流式] 推送SSE事件，内容长度: {len(content)}, 内容: {content}")
                                await sse_yield_func({
                                    'type': 'stream',
                                    'content': content,
                                    'node_id': node_id
                                })
                                # logger.info(f"[LLM流式] SSE事件推送成功")
                except asyncio.TimeoutError:
                    # logger.error(f"[LLM流式] chat_stream 调用超时")
                    raise
                
                # logger.info(f"[LLM流式] chat_stream 调用完成，共收到 {chunk_count} 个块，响应长度: {len(full_response)}")
                llm_response = full_response
        except Exception as e:
            logger.exception(f"[LLM流式] 调用大模型失败: {e}")

        if not llm_response:
            logger.warning("使用模拟响应")
            llm_response = await LangGraphExecutor._generate_mock_response(input_text, prompt, node_label)

        state = await LangGraphExecutor._parse_and_set_response(llm_response, node_data, state, actual_model, prompt)
        return state

    @staticmethod
    async def _generate_mock_response(input_text: str, prompt: str, node_label: str) -> str:
        """生成模拟响应（当大模型不可用时）"""
        return f"模拟响应: {node_label} - 处理输入: {input_text[:50]}..."

    @staticmethod
    async def _execute_skill_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行技能节点"""
        skill_id = node_data.get("skill_id", "")
        variables = state.get("variables", {})

        try:
            from base.plugins.agent.models.skill import Skill
            from base.plugins.agent.services.skill_service import SkillService

            skill = await Skill.get_or_none(id=skill_id, status="active")
            if skill:
                logger.debug(f"执行技能: {skill.name} (ID: {skill.id})")
                result = await SkillService.execute_skill(skill, variables)
                state["variables"]["skill_result"] = result
            else:
                logger.warning(f"技能不存在或未激活: skill_id={skill_id}")
                state["variables"]["skill_result"] = {"error": f"技能不存在或未激活: {skill_id}"}
        except Exception as e:
            logger.exception(f"执行技能失败: {e}")
            state["variables"]["skill_result"] = {"error": str(e)}

        return state

    @staticmethod
    async def _execute_tool_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具节点"""
        tool_name = node_data.get("tool_name", "")
        tool_params = node_data.get("tool_params", {})
        params = node_data.get("params", {})

        try:
            from base.plugins.agent.tools.registry import ToolRegistry

            variables = state.get("variables", {})
            
            final_params = {}
            all_params = {**tool_params, **params}
            for key, value in all_params.items():
                if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                    var_name = value[2:-2]
                    final_params[key] = variables.get(var_name, value)
                else:
                    final_params[key] = value

            tool_class = ToolRegistry.get_tool(tool_name)
            if tool_class:
                logger.debug(f"执行工具: {tool_name}")
                result = await tool_class.execute(**final_params)
                state["variables"][tool_name] = result
                state["variables"]["tool_result"] = result
            else:
                logger.warning(f"工具不存在: {tool_name}")
                state["variables"][tool_name] = {"error": f"工具不存在: {tool_name}"}
                state["variables"]["tool_result"] = {"error": f"工具不存在: {tool_name}"}
        except Exception as e:
            logger.exception(f"执行工具失败: {e}")
            state["variables"][tool_name] = {"error": str(e)}
            state["variables"]["tool_result"] = {"error": str(e)}

        return state

    @staticmethod
    async def _execute_condition_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行条件节点"""
        condition = node_data.get("condition", "")
        variables = state.get("variables", {})

        try:
            # 如果条件为空，直接返回False，条件节点的判断应该由边的条件表达式决定
            if not condition or condition.strip() == "":
                state["variables"]["condition_result"] = {
                    "condition": condition,
                    "result": False
                }
                return state
            
            # 将模板语法转换为可执行表达式
            import re
            
            def replace_template(match):
                path = match.group(1)
                parts = path.split('.')
                result = "get_var(variables"
                for part in parts:
                    result += f", '{part}'"
                result += ")"
                return result
            
            expr = re.sub(r'\{\{(\w+(\.\w+)*)\}\}', replace_template, condition)
            
            # 定义安全的变量获取函数
            def get_var(data, *keys):
                for key in keys:
                    if data is None or not isinstance(data, dict):
                        return None
                    data = data.get(key, None)
                return data
            
            logger.debug(f"条件节点执行: {condition} -> {expr}")
            result = safe_eval(expr, {"variables": variables, "get_var": get_var})
            state["variables"]["condition_result"] = {
                "condition": condition,
                "result": bool(result)
            }
        except Exception as e:
            logger.exception(f"条件表达式执行失败: {e}")
            state["variables"]["condition_result"] = {
                "condition": condition,
                "result": False,
                "error": str(e)
            }

        return state

    @staticmethod
    async def _execute_loop_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行循环节点"""
        loop_count = node_data.get("loop_count", 3)
        loop_var = node_data.get("loop_var", "loop_index")

        state["variables"]["loop_iterations"] = []
        for i in range(loop_count):
            state["variables"][loop_var] = i
            state["variables"]["loop_iterations"].append(i)

        return state

    @staticmethod
    async def _execute_iteration_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行迭代节点"""
        # 兼容前端字段名（iterationVariable）和后端字段名（iteration_var）
        iteration_var = node_data.get("iteration_var", node_data.get("iterationVariable", "item"))
        # 兼容前端字段名（iterationList）和后端字段名（collection_var）
        collection_var = node_data.get("collection_var", node_data.get("iterationList", "items"))

        collection = state.get("variables", {}).get(collection_var, [])
        if not isinstance(collection, list):
            collection = []

        total = len(collection)
        
        # 获取当前索引，如果不存在则从0开始，否则递增
        current_index = state.get("variables", {}).get("iteration_index", -1)
        
        # 检查是否已完成一轮迭代
        completed = state.get("variables", {}).get("iteration_completed", False)
        
        if current_index < 0 or completed:
            # 首次执行或已完成一轮，重新开始
            current_index = 0
            state["variables"]["iteration_results"] = []
            state["variables"]["iteration_completed"] = False
        else:
            # 继续下一个元素
            current_index += 1
        
        # 检查是否完成迭代
        if current_index >= total:
            state["variables"]["iteration_completed"] = True
            current_index = total  # 设置为total，用于条件判断
        
        state["variables"]["iteration_index"] = current_index
        state["variables"]["iteration_count"] = min(current_index + 1, total)
        state["variables"]["iteration_total"] = total

        # 设置当前迭代元素
        if collection and current_index < total:
            state["variables"][iteration_var] = collection[current_index]
            # 将当前元素添加到结果列表
            results = state.get("variables", {}).get("iteration_results", [])
            results.append(collection[current_index])
            state["variables"]["iteration_results"] = results
        else:
            state["variables"][iteration_var] = ""

        return state

    @staticmethod
    async def _execute_http_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行HTTP请求节点"""
        url = node_data.get("url", "")
        method = node_data.get("method", "GET")
        headers = node_data.get("headers", "")
        body = node_data.get("body", "")
        output_var = node_data.get("outputVar", "http_response")
        logger.info(f"进入http节点,请求: {method} {url} {headers} {body}")
        
        try:
            import json
            if isinstance(headers, str) and headers.strip():
                try:
                    headers = json.loads(headers)
                except json.JSONDecodeError:
                    headers = {}
            elif not isinstance(headers, dict):
                headers = {}
        except Exception as e:
            logger.warning(f"解析headers失败: {e}")
            headers = {}
            
        try:
            import aiohttp

            variables = state.get("variables", {})
            for key, value in variables.items():
                url = url.replace(f"{{{{{key}}}}}", str(value))
                if isinstance(body, str):
                    body = body.replace(f"{{{{{key}}}}}", str(value))
                if isinstance(headers, dict):
                    for h_key, h_value in headers.items():
                        if isinstance(h_value, str):
                            headers[h_key] = h_value.replace(f"{{{{{key}}}}}", str(value))

            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, data=body) as response:
                    content_type = response.headers.get("Content-Type", "")
                    response_text = await response.text()
                    
                    response_data = response_text
                    if "application/json" in content_type or "application/javascript" in content_type:
                        try:
                            import json
                            response_data = json.loads(response_text)
                        except json.JSONDecodeError:
                            pass
                    
                    state["variables"][output_var] = {
                        "status": response.status,
                        "content_type": content_type,
                        "data": response_data
                    }
                    logger.info(f"HTTP响应: {content_type}, 输出变量: {output_var}")
        except Exception as e:
            logger.exception(f"HTTP请求失败: {e}")
            state["variables"][output_var] = {"error": str(e)}

        return state

    @staticmethod
    async def _execute_code_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行代码节点"""
        code = node_data.get("code", "")

        try:
            variables = state.get("variables", {})
            local_vars = variables.copy()
            exec(code, {}, local_vars)
            state["variables"].update(local_vars)
        except Exception as e:
            logger.exception(f"代码执行失败: {e}")
            state["variables"]["code_error"] = str(e)

        return state

    @staticmethod
    async def _execute_template_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行模板节点"""
        template = node_data.get("template", "")
        output_var = node_data.get("outputVar", "template_output")

        variables = state.get("variables", {})
        
        # 调试日志
        logger.info(f"[模板节点] 开始执行")
        logger.info(f"[模板节点] template: {template}")
        logger.info(f"[模板节点] outputVar: {output_var}")
        logger.info(f"[模板节点] 可用变量: {list(variables.keys())}")
        if "result" in variables:
            logger.info(f"[模板节点] result 变量类型: {type(variables['result'])}")
            logger.info(f"[模板节点] result 变量值: {variables['result']}")
        
        # 支持嵌套属性访问，如 {{result.name}}
        import re
        
        def replace_template(match):
            path = match.group(1)
            parts = path.split('.')
            value = variables
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, None)
                elif isinstance(value, object) and hasattr(value, part):
                    value = getattr(value, part)
                else:
                    value = None
                    break
            return str(value) if value is not None else match.group(0)
        
        template = re.sub(r'\{\{(\w+(\.\w+)*)\}\}', replace_template, template)

        state["variables"][output_var] = template
        return state

    @staticmethod
    async def _execute_variable_aggregator_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行变量聚合器节点"""
        input_vars = node_data.get("input_vars", node_data.get("inputVars", []))
        output_var = node_data.get("outputVar", "aggregated")

        aggregated = {}
        variables = state.get("variables", {})

        # 支持多种输入格式
        if isinstance(input_vars, str):
            # 支持逗号分隔或换行分隔
            if ',' in input_vars:
                input_vars = [v.strip() for v in input_vars.split(",") if v.strip()]
            else:
                input_vars = [v.strip() for v in input_vars.split('\n') if v.strip()]
        elif isinstance(input_vars, dict):
            # 重命名映射: {"name": "user_name", "age": "user_age"}
            for source_var, target_name in input_vars.items():
                if source_var in variables:
                    aggregated[target_name] = variables[source_var]
            state["variables"][output_var] = aggregated
            return state

        # 列表格式: ["name", "age"]
        if isinstance(input_vars, list):
            for var_name in input_vars:
                if var_name in variables:
                    aggregated[var_name] = variables[var_name]

        state["variables"][output_var] = aggregated
        return state

    @staticmethod
    async def _execute_document_extractor_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行文档提取节点
        
        支持两种模式：
        1. 简单模式：使用 extract_fields 指定字段名，从文档中提取前100字符
        2. 正则模式：使用 patterns 指定正则表达式，提取匹配内容
        """
        # 兼容前端字段名
        document_var = node_data.get("document_var", node_data.get("documentVar", "document"))
        extract_fields = node_data.get("extract_fields", node_data.get("extractFields", []))
        output_var = node_data.get("outputVar", "extracted_data")
        patterns = node_data.get("patterns", node_data.get("rules", []))
        
        # 兼容前端 extractRules 字段（可能是字符串或数组）
        extract_rules = node_data.get("extractRules", None)
        if extract_rules and not patterns:
            if isinstance(extract_rules, list):
                patterns = extract_rules
            elif isinstance(extract_rules, str):
                # 尝试解析JSON数组
                try:
                    import json
                    patterns = json.loads(extract_rules)
                except (json.JSONDecodeError, ValueError):
                    # 按行分割
                    patterns = [line.strip() for line in extract_rules.split('\n') if line.strip()]

        document = state.get("variables", {}).get(document_var, "")
        
        # 如果文档是字典或其他非字符串类型，转换为字符串
        if not isinstance(document, str):
            import json
            document = json.dumps(document, ensure_ascii=False)
        
        # 调试日志
        logger.info(f"[文档提取] document_var: {document_var}, document长度: {len(document) if document else 0}")
        logger.info(f"[文档提取] extract_fields: {extract_fields}")
        logger.info(f"[文档提取] patterns: {patterns}")
        logger.info(f"[文档提取] extractRules: {extract_rules}")
        logger.info(f"[文档提取] document[:200]: {document[:200] if document else ''}")

        # 使用正则表达式提取
        if patterns and isinstance(patterns, list):
            import re
            extracted = {}
            for i, pattern in enumerate(patterns):
                try:
                    # 使用 DOTALL 模式使 . 匹配换行符
                    matches = re.findall(pattern, document, re.DOTALL)
                    if matches:
                        # 如果匹配到多个结果，保存为列表；否则保存单个值
                        extracted_value = matches if len(matches) > 1 else matches[0]
                    else:
                        extracted_value = ""
                    
                    # 使用字段名或默认名称
                    field_name = extract_fields[i] if i < len(extract_fields) else f"field_{i}"
                    extracted[field_name] = extracted_value
                    logger.info(f"[文档提取] 字段 '{field_name}' 提取结果: {repr(extracted_value)[:100]}")
                except re.error as e:
                    logger.error(f"[文档提取] 正则表达式错误: {pattern}, {e}")
                    field_name = extract_fields[i] if i < len(extract_fields) else f"field_{i}"
                    extracted[field_name] = ""
            
            state["variables"][output_var] = extracted
            logger.info(f"[文档提取] 正则模式提取结果: {extracted}")
        else:
            # 兼容原有简单模式：每个字段取前100字符
            extracted = {}
            for field in extract_fields:
                extracted[field] = document[:100] if document else ""
            
            state["variables"][output_var] = extracted
            logger.info(f"[文档提取] 简单模式提取结果: {extracted}")

        return state

    @staticmethod
    async def _execute_variable_assigner_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行变量赋值节点"""
        # 兼容前端字段名（varName）和后端字段名（variable_name）
        variable_name = node_data.get("variable_name", node_data.get("varName", ""))
        # 兼容前端字段名（varValue）和后端字段名（value）
        value = node_data.get("value", node_data.get("varValue", ""))
        
        # 调试日志
        logger.info(f"[变量赋值] varName: {variable_name}, varValue: {repr(value)}, 类型: {type(value)}")

        variables = state.get("variables", {})
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            var_name = value[2:-2]
            value = variables.get(var_name, value)
        
        # 尝试解析JSON字符串
        if isinstance(value, str) and (value.startswith("[") or value.startswith("{")):
            try:
                import json
                value = json.loads(value)
                logger.info(f"[变量赋值] JSON解析成功: {value}, 类型: {type(value)}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.info(f"[变量赋值] 首次JSON解析失败: {e}")
                # 尝试处理转义的引号
                if '\\"' in value:
                    try:
                        value = value.replace('\\"', '"')
                        value = json.loads(value)
                        logger.info(f"[变量赋值] 处理转义引号后解析成功: {value}, 类型: {type(value)}")
                    except (json.JSONDecodeError, ValueError) as e2:
                        logger.info(f"[变量赋值] 处理转义引号后仍然失败: {e2}")

        state["variables"][variable_name] = value
        return state

    @staticmethod
    async def _execute_parameter_extractor_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行参数提取节点
        
        从输入变量（字典类型）中提取指定的参数字段
        """
        # 兼容前端字段名
        source_var = node_data.get("source_var", node_data.get("inputVariable", ""))
        parameter_name = node_data.get("parameter_name", node_data.get("parameters", ""))
        output_var = node_data.get("outputVar", "")
        
        # 如果没有指定输出变量，使用parameter_name作为输出变量名
        if not output_var:
            output_var = parameter_name

        source = state.get("variables", {}).get(source_var, "")
        
        # 调试日志
        logger.info(f"[参数提取] source_var: {source_var}, parameter_name: {parameter_name}, output_var: {output_var}")
        logger.info(f"[参数提取] source值: {source}, 类型: {type(source)}")
        
        if isinstance(source, dict):
            state["variables"][output_var] = source.get(parameter_name, "")
            logger.info(f"[参数提取] 提取成功: {state['variables'][output_var]}")
        else:
            # 如果源不是字典，尝试解析为JSON
            if isinstance(source, str):
                try:
                    import json
                    source = json.loads(source)
                    if isinstance(source, dict):
                        state["variables"][output_var] = source.get(parameter_name, "")
                        logger.info(f"[参数提取] JSON解析后提取成功: {state['variables'][output_var]}")
                    else:
                        state["variables"][output_var] = ""
                except (json.JSONDecodeError, ValueError):
                    state["variables"][output_var] = ""
            else:
                state["variables"][output_var] = ""
            
            logger.info(f"[参数提取] 提取结果: {state['variables'][output_var]}")

        return state

    @staticmethod
    async def _execute_json_extractor_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行JSON提取节点"""
        source_var = node_data.get("inputVariable", "")
        output_var = node_data.get("outputVar", "extracted_json")

        source = state.get("variables", {}).get(source_var, "")

        try:
            if isinstance(source, str):
                source = json.loads(source)

            state["variables"][output_var] = source
        except Exception as e:
            logger.exception(f"JSON提取失败: {e}")
            state["variables"][output_var] = None

        return state

    @staticmethod
    async def _execute_parallel_node(current_node: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行并行节点 - 自动将后续节点作为并行分支"""
        node_data = current_node.get("data", {})
        output_var = node_data.get("outputVar", "parallel_results")
        current_node_id = current_node.get("id", "")
        logger.info(f"[并行节点] 开始执行，节点ID: {current_node_id}")
        
        # 从状态中获取图结构
        flow_data = state.get("flow_data", {})
        edges = flow_data.get("edges", [])
        nodes_map = {node.get("id"): node for node in flow_data.get("nodes", [])}
        logger.info(f"[并行节点] 图结构 - 边数: {len(edges)}, 节点数: {len(nodes_map)}")
        
        # 获取分支配置（支持JSON字符串和列表）
        branches = node_data.get("branches", [])
        if isinstance(branches, str) and branches.strip():
            try:
                import json
                branches = json.loads(branches)
            except json.JSONDecodeError as e:
                logger.error(f"[并行节点] 解析 branches JSON 失败: {e}")
                branches = []
        
        # 如果没有手动配置分支，自动从边构建分支
        if not branches and current_node_id and edges:
            outgoing_edges = [edge for edge in edges if edge.get("source") == current_node_id]
            logger.info(f"[并行节点] 出边数: {len(outgoing_edges)}")
            
            if outgoing_edges:
                branches = []
                for edge in outgoing_edges:
                    target_node_id = edge.get("target", "")
                    target_node = nodes_map.get(target_node_id)
                    if target_node:
                        branch_name = target_node.get("data", {}).get("label", target_node_id)
                        branches.append({
                            "name": branch_name,
                            "nodes": [target_node]
                        })
                logger.info(f"[并行节点] 自动构建 {len(branches)} 个分支")
        
        logger.info(f"[并行节点] 最终分支数: {len(branches)}")

        async def execute_branch(branch_name: str, branch_nodes: List[Dict]) -> Dict[str, Any]:
            """执行单个分支"""
            logger.debug(f"[并行节点] 开始执行分支: {branch_name}")
            
            branch_state = {
                "variables": state["variables"].copy(),
                "node_results": {},
                "messages": [],
                "input": state.get("input", {}).copy() if isinstance(state.get("input"), dict) else state.get("input"),
                "output": {},
                "execution_trace": [],
                "current_node": None,
                "error": None
            }
            
            try:
                for node in branch_nodes:
                    node_type = node.get("type", "")
                    node_data_item = node.get("data", {})
                    node_id = node.get("id", f"{branch_name}_node_{len(branch_state['execution_trace'])}")
                    
                    logger.debug(f"[并行节点] 分支 {branch_name} 执行节点: {node_id} ({node_type})")
                    
                    if node_type == "llm":
                        branch_state = await LangGraphExecutor._execute_llm_node(node, branch_state)
                    elif node_type == "tool":
                        branch_state = await LangGraphExecutor._execute_tool_node(node_data_item, branch_state)
                    elif node_type == "http":
                        branch_state = await LangGraphExecutor._execute_http_node(node_data_item, branch_state)
                    elif node_type == "code":
                        branch_state = await LangGraphExecutor._execute_code_node(node_data_item, branch_state)
                    elif node_type == "skill":
                        branch_state = await LangGraphExecutor._execute_skill_node(node_data_item, branch_state)
                    elif node_type == "template":
                        branch_state = await LangGraphExecutor._execute_template_node(node_data_item, branch_state)
                    else:
                        logger.warning(f"[并行节点] 分支 {branch_name} 遇到未知节点类型: {node_type}")
                    
                    branch_state["execution_trace"].append({
                        "node_id": node_id,
                        "node_type": node_type,
                        "timestamp": datetime.now().isoformat()
                    })
                
                logger.debug(f"[并行节点] 分支 {branch_name} 执行完成")
                return {branch_name: branch_state["variables"]}
            
            except Exception as e:
                logger.exception(f"[并行节点] 分支 {branch_name} 执行失败: {e}")
                return {branch_name: {"error": str(e), "success": False}}

        if branches:
            tasks = []
            for branch in branches:
                branch_name = branch.get("name", f"branch_{len(tasks)}")
                branch_nodes = branch.get("nodes", [])
                if branch_nodes:
                    tasks.append(execute_branch(branch_name, branch_nodes))
                    logger.debug(f"[并行节点] 添加分支任务: {branch_name}")
            
            if tasks:
                logger.info(f"[并行节点] 开始并发执行 {len(tasks)} 个分支任务")
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    merged_results = {}
                    success_count = 0
                    fail_count = 0
                    
                    for result in results:
                        if isinstance(result, Exception):
                            logger.error(f"[并行节点] 分支执行异常: {result}")
                            fail_count += 1
                        else:
                            merged_results.update(result)
                            success_count += 1
                    
                    state["variables"][output_var] = merged_results
                    state["variables"][f"{output_var}_summary"] = {
                        "total_branches": len(tasks),
                        "success_count": success_count,
                        "fail_count": fail_count,
                        "completed_at": datetime.now().isoformat()
                    }
                    
                    logger.info(f"[并行节点] 执行完成，成功: {success_count}, 失败: {fail_count}")
                except Exception as e:
                    logger.exception(f"[并行节点] 并发执行失败: {e}")
                    state["variables"][output_var] = {"error": str(e)}
        
        else:
            logger.warning(f"[并行节点] 没有配置任何分支")
        
        return state

    @staticmethod
    async def _execute_default_node(node_data: Dict, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行默认节点"""
        logger.warning(f"未知节点类型，跳过执行")
        return state