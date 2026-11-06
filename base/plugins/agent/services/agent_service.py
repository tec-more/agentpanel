"""
Agent service
"""
from typing import List, Optional, AsyncGenerator, Dict, Any
from tortoise.exceptions import DoesNotExist
from base.plugins.agent.models.agent import Agent
from base.plugins.agent.schemas.agent import AgentCreate, AgentUpdate
import json
import asyncio
from datetime import datetime
import logging
logger = logging.getLogger(__name__)


class AgentService:
    model = "agent"
    """Agent service class"""

    @staticmethod
    async def create_agent(agent_data: AgentCreate) -> Agent:
        """Create agent"""
        agent = await Agent.create(
            name=agent_data.name,
            description=agent_data.description,
            status=agent_data.status,
            config=agent_data.config,
            memory_capacity=agent_data.memory_capacity
        )

        return agent

    @staticmethod
    async def get_agents(skip: int = 0, limit: int = 100, name: str = "", status: str = "") -> List[Agent]:
        """Get agent list"""
        query = Agent.all()
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        agents = await query.offset(skip).limit(limit)
        return agents

    @staticmethod
    async def get_agent_by_id(agent_id: int) -> Optional[Agent]:
        """Get agent by ID"""
        try:
            agent = await Agent.get(id=agent_id)
            return agent
        except DoesNotExist:
            return None

    @staticmethod
    async def update_agent(agent_id: int, agent_data: AgentUpdate) -> Optional[Agent]:
        """Update agent"""
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            return None

        update_data = agent_data.model_dump(exclude_unset=True)

        await agent.update_from_dict(update_data)
        await agent.save()

        return agent

    @staticmethod
    async def delete_agent(agent_id: int) -> bool:
        """Delete agent"""
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent:
            return False

        await agent.delete()
        return True



    @staticmethod
    async def execute_agent(agent_id: int, input_data: dict, actor: dict, execution_id: str = None) -> dict:
        """
        执行智能体
        使用结构图（LangGraph的具现化）来实现智能体内部的逻辑控制
        结构图存储在 graph_definition 字段中
        """
        agent = await AgentService.get_agent_by_id(agent_id)
        if not agent or agent.status != "active":
            return {"success": False, "message": "Agent not found or inactive"}

        try:
            from base.plugins.agent.services.langgraph_executor import LangGraphExecutor
            result = await LangGraphExecutor.execute_agent(agent, input_data, actor,execution_id=execution_id)
            return result

        except Exception as e:
            import traceback
            return {"success": False, "message": str(e), "traceback": traceback.format_exc()}

    @staticmethod
    def _transform_node(node: dict) -> dict:
        """转换节点格式：模板格式 -> 系统格式"""
        transformed = {
            'id': node.get('id'),
            'type': node.get('type'),
            'position': node.get('position', {'x': 0, 'y': 0}),
            'data': {
                'label': node.get('name') or node.get('data', {}).get('label') or '节点',
                'description': node.get('data', {}).get('description', '')
            }
        }

        node_type = node.get('type')
        if node_type == 'llm':
            config = node.get('config', {})
            data = node.get('data', {})
            transformed['data']['prompt'] = config.get('prompt') or data.get('prompt', '')
            transformed['data']['modelId'] = config.get('model_id') or data.get('modelId')
            transformed['data']['temperature'] = data.get('temperature', 0.7)
            transformed['data']['maxTokens'] = data.get('maxTokens', 1024)
            transformed['data']['stream'] = data.get('stream', False)
            transformed['data']['outputVar'] = data.get('outputVar', '')
        elif node_type == 'tool':
            config = node.get('config', {})
            data = node.get('data', {})
            transformed['data']['toolName'] = config.get('tool_name') or data.get('toolName', '')
            transformed['data']['description'] = config.get('description') or data.get('description', '')
        elif node_type == 'decision' or node_type == 'condition':
            transformed['type'] = 'condition'
            config = node.get('config', {})
            data = node.get('data', {})
            transformed['data']['condition'] = config.get('condition') or data.get('condition', '')

        return transformed

    @staticmethod
    def _transform_edge(edge: dict, index: int) -> dict:
        """转换边格式：模板格式 -> 系统格式"""
        return {
            'id': edge.get('id') or f"{edge.get('source')}-{edge.get('target')}-{index}",
            'source': edge.get('source'),
            'target': edge.get('target'),
            'sourceHandle': edge.get('sourceHandle'),
            'targetHandle': edge.get('targetHandle'),
            'condition': edge.get('condition')
        }

    @staticmethod
    async def import_agent(import_data: dict) -> Agent:
        """
        导入智能体完整配置
        支持的格式：
        {
          "agent": { ... },
          "tools": [...],
          "skills": [...],
          "rag": {...}
        }
        或直接传入 agent 配置
        """
        agent_data = import_data.get('agent') or import_data

        graph_definition = agent_data.get('graph_definition', {'nodes': [], 'edges': []})
        if graph_definition and 'nodes' in graph_definition:
            graph_definition['nodes'] = [
                AgentService._transform_node(node)
                for node in graph_definition['nodes']
            ]
        if graph_definition and 'edges' in graph_definition:
            graph_definition['edges'] = [
                AgentService._transform_edge(edge, index)
                for index, edge in enumerate(graph_definition['edges'])
            ]

        agent = await Agent.create(
            name=agent_data.get('name', '导入的智能体'),
            description=agent_data.get('description', ''),
            status=agent_data.get('status', 'active'),
            memory_capacity=agent_data.get('memory_capacity', 100),
            default_memory_mode=agent_data.get('default_memory_mode', 'public'),
            graph_definition=graph_definition
        )

        return agent

    @staticmethod
    def should_use_sse(agent: Agent) -> bool:
        """
        判断智能体是否应该使用 SSE 模式执行

        判断条件：
        1. 有流式 LLM 节点（stream=True）
        2. 有工具/HTTP/技能节点（可能需要等待外部响应）
        3. 有条件分支或循环节点（需要多轮执行）

        Args:
            agent: 智能体对象

        Returns:
            是否应该使用 SSE 模式
        """
        graph = agent.graph_definition
        if not graph or 'nodes' not in graph:
            return False

        nodes = graph.get('nodes', [])

        for node in nodes:
            stream_val = node.get('data', {}).get('stream')
            is_streaming = stream_val is True or (isinstance(stream_val, str) and stream_val.lower() == 'true')
            if node.get('type') == 'llm' and is_streaming:
                return True

        for node in nodes:
            if node.get('type') in ('tool', 'http', 'skill'):
                return True

        has_condition = any(n.get('type') == 'condition' for n in nodes)
        has_loop = any(n.get('type') in ('loop', 'iteration') for n in nodes)
        if has_condition or has_loop:
            return True

        return False

    @staticmethod
    async def sse_execution_generator(
        agent: Agent,
        input_data: Dict[str, Any],
        execution_id: str,
        execution_manager: dict,
        actor: dict
    ) -> AsyncGenerator[str, None]:
        """
        SSE事件生成器 - 实时推送执行过程（支持边思考边输出）

        Args:
            agent: 智能体对象
            input_data: 输入数据
            execution_id: 执行ID
            execution_manager: 执行管理器（用于检查取消状态）

        Returns:
            SSE事件流
        """
        from base.plugins.agent.services.langgraph_executor import LangGraphExecutor

        logger.info(f"[Execution] 开始执行，execution_id: {execution_id}")

        def send_event(event_data):
            """SSE数据推送helper"""
            return f"data: {json.dumps({**event_data, 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

        async def check_cancelled():
            """检查是否被取消"""
            exec_info = execution_manager.get(execution_id)
            return exec_info and exec_info.get('is_cancelled', False)

        try:
            yield send_event({'type': 'start', 'execution_id': execution_id, 'message': '开始执行智能体'})
            class SSEQueue:
                def __init__(self):
                    self.queue = asyncio.Queue()

                async def put(self, event):
                    await self.queue.put(event)

                async def get(self):
                    return await self.queue.get()

                def empty(self):
                    return self.queue.empty()

            logger.info(f"[SSE生成器] 开始初始化，execution_id={execution_id}")
            sse_queue = SSEQueue()

            async def wrapped_sse_yield(event):
                # logger.info(f"[agent API] wrapped_sse_yield 收到事件: {event}")
                await sse_queue.put(event)
                # logger.info(f"[agent API] 事件已入队列，队列大小: {sse_queue.queue.qsize()}")

            sse_yield_call_count = [0]

            async def wrapped_sse_yield_with_counter(event):
                sse_yield_call_count[0] += 1
                count = sse_yield_call_count[0]
                # logger.info(f"[agent API] wrapped_sse_yield 调用 #{count}: {event}")
                await sse_queue.put(event)
                # logger.info(f"[agent API] 事件已入队列 #{count}，队列大小: {sse_queue.queue.qsize()}")

            async def execute_task():
                logger.info(f"[SSE生成器] execute_task 开始执行")
                try:
                    exec_info = execution_manager.get(execution_id, {})
                    llm_resources = exec_info.get('_llm_resources', {})
                    skill_resources = exec_info.get('_skill_resources', {})
                    logger.info(f"[SSE生成器] 获取预加载资源: LLM={len(llm_resources)}, 技能={len(skill_resources)}")

                    logger.info(f"[SSE生成器] 开始调用 LangGraphExecutor.execute_agent")
                    logger.info(f"[SSE生成器] 准备 await execute_agent...")
                    result = await LangGraphExecutor.execute_agent(
                        agent=agent,
                        input_data=input_data,
                        actor=actor,
                        sse_yield_func=wrapped_sse_yield_with_counter,
                        execution_id=execution_id,
                        llm_resources=llm_resources,
                        skill_resources=skill_resources,
                    )
                    return result
                except Exception as e:
                    logger.error(f"[SSE生成器] LangGraph 执行异常: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {
                        "success": False,
                        "message": str(e),
                        "traceback": traceback.format_exc()
                    }

            logger.info("=" * 50)
            logger.info("[SSE生成器] ===== START =====")
            logger.info("=" * 50)
            task = asyncio.create_task(execute_task())
            logger.info(f"[SSE生成器] task 创建: {task}")

            yield send_event({'type': 'info', 'label': '初始化', 'message': '初始化执行环境...'})

            done = False
            last_activity = asyncio.get_event_loop().time()
            import time
            loop_start_time = time.time()
            last_log_time = loop_start_time
            loop_count = 0

            while not done or not sse_queue.empty():
                loop_count += 1
                try:
                    current_time = asyncio.get_event_loop().time()

                    current_elapsed = time.time() - loop_start_time
                    
                    if current_elapsed - last_log_time >= 5.0:
                        last_log_time = current_elapsed

                    if await check_cancelled():
                        yield send_event({'type': 'cancelled', 'message': '执行被用户中断'})
                        task.cancel()
                        break

                    if task.done():
                        task_exception = task.exception()
                        if task_exception:
                            yield send_event({'type': 'error', 'message': f'执行异常: {str(task_exception)}'})
                            break

                    if current_time - last_activity > 300:
                        yield send_event({'type': 'error', 'message': '执行超时，请重试'})
                        task.cancel()
                        break

                    try:
                        if not sse_queue.empty():
                            event = await asyncio.wait_for(sse_queue.get(), timeout=1.0)
                            # logger.info(f"[SSE Loop] 从队列获取事件发送: {event}")
                            yield send_event(event)
                            last_activity = current_time
                        elif not task.done():
                            last_activity = current_time
                            await asyncio.sleep(0.01)
                    except asyncio.TimeoutError:
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        pass

                    if task.done() and sse_queue.empty():
                        done = True
                        # logger.info(f"[SSE Loop] 循环 #{loop_count}, elapsed={current_elapsed:.1f}s, task.done={task.done()}, done={done}, queue.empty={sse_queue.empty()}")
                        logger.info("[Execution] 任务已完成，队列已空，退出循环")

                except Exception as e:
                    logger.error(f"[SSE 推送异常] {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    break

            logger.info("[Execution] while循环已退出，准备获取task结果")
            try:
                logger.info(f"[Execution] 检查task状态: cancelled={task.cancelled()}, done={task.done()}")
                if not task.cancelled():
                    logger.info("[Execution] 开始 await task")
                    result = await task
                    logger.info(f"[Execution] await task 完成，result.success={result.get('success')}")

                    variables_summary = {}
                    variables = result.get('variables', {})
                    for key, value in list(variables.items())[:5]:
                        if key == 'llm_output':
                            llm_str = str(value)
                            variables_summary[key] = {
                                'type': 'large_text',
                                'length': len(llm_str),
                                'preview': llm_str[:100] + '...' if len(llm_str) > 100 else llm_str
                            }
                        else:
                            variables_summary[key] = value

                    logger.info("[Execution] 准备发送 complete 事件")
                    yield send_event({
                        'type': 'complete',
                        'result': result.get('output', {}),
                        'variables': variables_summary
                    })
                    logger.info("[Execution] complete 事件已发送")
                else:
                    logger.warning("[Execution] task已被取消，跳过获取结果")
            except Exception as e:
                logger.error(f"获取执行结果失败: {e}")
                yield send_event({'type': 'error', 'message': str(e)})

        except Exception as e:
            import traceback
            yield send_event({'type': 'error', 'message': str(e), 'traceback': traceback.format_exc()})
