"""
Workflow service
"""
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from tortoise.exceptions import DoesNotExist
from tortoise.expressions import Q
from tortoise.functions import Max
from tortoise.transactions import in_transaction

from base.common.authz import (
    OwnerContext,
    ResourceGrantService,
    get_owned_or_404,
    owned_queryset,
)
from base.common.authz.filter import is_accessible
from base.plugins.agent.models.workflow import Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution
from base.plugins.agent.models.workflow_version import WorkflowVersion
from base.plugins.agent.models.agent import Agent
from base.plugins.agent.models.skill import Skill
from base.plugins.llm.models.model import LLMModel
from base.plugins.agent.schemas.workflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowExecutionCreate
)
from base.plugins.agent.services.graph_validator import (
    DOMAIN_ADMIN,
    DOMAIN_USER,
    collect_resource_refs,
    has_blocking_errors,
    validate_graph,
)

# ============================================================
# M3 草稿/发布异常（错误码段位 409xx/422xx，docs/arch/04 §2.3）
# ============================================================


class DraftConflictError(Exception):
    """草稿乐观锁冲突（40901）：draft_version 与服务端不一致"""

    def __init__(self, current_version: int):
        self.current_version = current_version
        super().__init__("草稿版本冲突，请刷新后重试")


class ValidationBlockedError(Exception):
    """发布校验阻断（422xx）：携带 E-1xx 结构化错误明细（R-15）"""

    def __init__(self, issues: List[Dict[str, Any]]):
        self.issues = list(issues)
        super().__init__("校验未通过，存在阻断级错误")


class WorkflowStateError(Exception):
    """状态冲突（409xx）：如删除存在生效发布态的工作流"""


class _IdempotencyStore:
    """
    发布幂等键存储（04-§5.2：idempotency_key 24h 去重）

    Redis 可用时落 Redis（quota_ 同款用法）；不可用时进程内字典兜底（单实例私有化部署）。
    存储值：发布成功响应载荷；重放直接返回原响应（幂等）。
    """

    _mem: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    TTL_SECONDS = 86400  # 24h

    @classmethod
    async def _redis(cls):
        try:
            from base.common.cache import RedisCache
            if not RedisCache.is_enabled():
                return None
            cache = await RedisCache.get_instance()
            return cache._client  # noqa: SLF001（与 quota_service 一致的既有用法）
        except Exception:
            return None

    @classmethod
    async def get(cls, key: str) -> Optional[Dict[str, Any]]:
        redis = await cls._redis()
        if redis is not None:
            try:
                import json as _json
                raw = await redis.get(f"idem:{key}")
                return _json.loads(raw) if raw else None
            except Exception:
                pass
        hit = cls._mem.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
        cls._mem.pop(key, None)
        return None

    @classmethod
    async def set(cls, key: str, payload: Dict[str, Any]) -> None:
        redis = await cls._redis()
        if redis is not None:
            try:
                import json as _json
                await redis.set(f"idem:{key}", _json.dumps(payload, ensure_ascii=False),
                                ex=cls.TTL_SECONDS)
                return
            except Exception:
                pass
        cls._mem[key] = (time.time() + cls.TTL_SECONDS, payload)

# Try to import LangGraph and LangChain
try:
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# Try to import HTTP libraries
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Try to import code execution libraries
try:
    import json
    import re
    JSON_AVAILABLE = True
except ImportError:
    JSON_AVAILABLE = False


class WorkflowService:
    model = "workflow"
    """Workflow service class"""

    @staticmethod
    async def create_workflow(workflow_data: WorkflowCreate, owner: Optional[OwnerContext] = None) -> Workflow:
        """Create workflow（携带归属；v2 图自动识别 schema_version）"""
        definition = workflow_data.definition or {}
        schema_version = "v2" if (
            isinstance(definition, dict) and definition.get("schema_version") in (2, "2", "v2")
        ) else "v1"
        workflow = await Workflow.create(
            name=workflow_data.name,
            description=workflow_data.description,
            status=workflow_data.status,
            definition=definition,
            schema_version=schema_version,
            owner_type=owner.owner_type if owner is not None else "usr",
            owner_id=owner.owner_id if owner is not None else None,
        )
        return workflow

    @staticmethod
    async def get_workflows(skip: int = 0, limit: int = 100, name: str = "", status: str = "",
                            owner: Optional[OwnerContext] = None) -> List[Workflow]:
        """Get workflow list（R-01：归属过滤后的可见集合）"""
        query = owned_queryset(Workflow, owner) if owner is not None else Workflow.all()
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        workflows = await query.offset(skip).limit(limit).prefetch_related('nodes', 'edges')
        return workflows

    @staticmethod
    async def count_workflows(name: str = "", status: str = "",
                              owner: Optional[OwnerContext] = None) -> int:
        """统计归属过滤后的工作流总数（BUG-T15-005：列表契约 items+total）"""
        query = owned_queryset(Workflow, owner) if owner is not None else Workflow.all()
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        return await query.count()

    @staticmethod
    async def get_workflow_by_id(workflow_id: int, owner: Optional[OwnerContext] = None,
                                 *, include_public: bool = False,
                                 for_write: bool = False) -> Optional[Workflow]:
        """Get workflow by ID（携带 owner 时走强归属校验，越权 404）"""
        if owner is not None:
            return await get_owned_or_404(
                Workflow, workflow_id, owner,
                include_public=include_public, for_write=for_write,
            )
        try:
            workflow = await Workflow.get(id=workflow_id).prefetch_related('nodes', 'edges')
            return workflow
        except DoesNotExist:
            return None

    @staticmethod
    async def update_workflow(workflow_id: int, workflow_data: WorkflowUpdate,
                              owner: Optional[OwnerContext] = None) -> Optional[Workflow]:
        """Update workflow（写操作强归属）"""
        workflow = await WorkflowService.get_workflow_by_id(workflow_id, owner, for_write=True)
        if not workflow:
            return None

        update_data = workflow_data.model_dump(exclude_unset=True)

        await workflow.update_from_dict(update_data)
        await workflow.save()

        return workflow

    @staticmethod
    async def delete_workflow(workflow_id: int, owner: Optional[OwnerContext] = None) -> bool:
        """Delete workflow（有生效发布态需先停用，PRD §6.4-B5/04-§2.1）"""
        workflow = await WorkflowService.get_workflow_by_id(workflow_id, owner, for_write=True)
        if not workflow:
            return False

        if workflow.current_version_id is not None and workflow.status == "active":
            raise WorkflowStateError("工作流存在生效发布态，需先停用后再删除")

        # Delete associated nodes and edges
        await WorkflowNode.filter(workflow=workflow).delete()
        await WorkflowEdge.filter(workflow=workflow).delete()

        await workflow.delete()
        return True

    @staticmethod
    async def import_workflow(import_data: dict) -> Workflow:
        """
        导入工作流完整配置
        支持的格式：
        {
          "workflow": { ... },
          "nodes": [...],
          "edges": [...]
        }
        或直接传入 workflow 配置
        """
        workflow_data = import_data.get('workflow') or import_data

        definition = workflow_data.get('definition', {'nodes': [], 'edges': []})
        
        if not definition or 'nodes' not in definition:
            definition = {
                'nodes': workflow_data.get('nodes', []),
                'edges': workflow_data.get('edges', [])
            }

        workflow = await Workflow.create(
            name=workflow_data.get('name', '导入的工作流'),
            description=workflow_data.get('description', ''),
            status=workflow_data.get('status', 'draft'),
            definition=definition
        )

        return workflow

    @staticmethod
    async def create_workflow_node(workflow_id: int, node_data: Dict[str, Any]) -> WorkflowNode:
        """Create workflow node"""
        workflow = await WorkflowService.get_workflow_by_id(workflow_id)
        if not workflow:
            raise ValueError("Workflow not found")
        
        node = await WorkflowNode.create(
            workflow=workflow,
            name=node_data['name'],
            type=node_data['type'],
            config=node_data['config'],
            position=node_data['position'],
            agent_id=node_data.get('agent_id'),
            skill_id=node_data.get('skill_id')
        )
        
        return node

    @staticmethod
    async def create_workflow_edge(workflow_id: int, edge_data: Dict[str, Any]) -> WorkflowEdge:
        """Create workflow edge"""
        workflow = await WorkflowService.get_workflow_by_id(workflow_id)
        if not workflow:
            raise ValueError("Workflow not found")
        
        source_node = await WorkflowNode.get(id=edge_data['source_node_id'])
        target_node = await WorkflowNode.get(id=edge_data['target_node_id'])
        
        edge = await WorkflowEdge.create(
            workflow=workflow,
            source_node=source_node,
            target_node=target_node,
            condition=edge_data.get('condition'),
            label=edge_data.get('label')
        )
        
        return edge

    @staticmethod
    async def execute_workflow(workflow_id: int, input_data: Dict[str, Any]) -> WorkflowExecution:
        """Execute workflow"""
        workflow = await WorkflowService.get_workflow_by_id(workflow_id)
        if not workflow:
            raise ValueError("Workflow not found")
        
        # Create execution record
        execution = await WorkflowExecution.create(
            workflow=workflow,
            input_data=input_data,
            status="running"
        )
        
        try:
            # Build and execute the workflow using LangGraph
            output_data = await WorkflowService._build_and_execute_graph(workflow, input_data)
            
            # Update execution status
            from datetime import datetime
            await execution.update_from_dict({
                "status": "success",
                "output_data": output_data,
                "completed_at": datetime.now()
            })
            await execution.save()
        except Exception as e:
            # Update execution status with error
            from datetime import datetime
            await execution.update_from_dict({
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now()
            })
            await execution.save()
            raise
        
        return execution

    @staticmethod
    async def get_all_workflow_executions(skip: int = 0, limit: int = 100, status: str = "") -> List[WorkflowExecution]:
        """Get all workflow executions"""
        query = WorkflowExecution.all()
        
        if status:
            query = query.filter(status=status)
        
        executions = await query.offset(skip).limit(limit).order_by("-started_at")
        return executions

    @staticmethod
    async def get_workflow_executions(workflow_id: int, skip: int = 0, limit: int = 100, status: str = "") -> List[WorkflowExecution]:
        """Get workflow executions"""
        query = WorkflowExecution.filter(workflow_id=workflow_id)
        
        if status:
            query = query.filter(status=status)
        
        executions = await query.offset(skip).limit(limit).order_by("-started_at")
        return executions

    @staticmethod
    async def get_workflow_execution_by_id(execution_id: int) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID"""
        try:
            return await WorkflowExecution.get(id=execution_id)
        except DoesNotExist:
            return None

    @staticmethod
    async def _build_and_execute_graph(workflow: Workflow, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build and execute workflow graph using LangGraph"""
        if not LANGGRAPH_AVAILABLE:
            # LangGraph is not available, return a mock response
            return {
                "message": "LangGraph is not available",
                "input_data": input_data,
                "workflow_name": workflow.name
            }
        
        # Create a StateGraph
        graph = StateGraph(Dict[str, Any])
        
        # Add nodes to the graph
        for node in workflow.nodes:
            if node.type == "agent":
                # Add agent node
                agent = await node.agent
                if agent:
                    graph.add_node(node.name, lambda state: WorkflowService._execute_agent_node(agent, state))
            elif node.type == "skill":
                # Add skill node
                skill = await node.skill
                if skill:
                    graph.add_node(node.name, lambda state: WorkflowService._execute_skill_node(skill, state))
            elif node.type == "llm":
                # Add LLM node
                llm = await node.llm
                if llm:
                    graph.add_node(node.name, lambda state: WorkflowService._execute_llm_node(llm, state))
            elif node.type == "decision":
                # Add decision node
                graph.add_node(node.name, lambda state: WorkflowService._execute_decision_node(node, state))
            elif node.type == "fork":
                # Add fork node
                graph.add_node(node.name, lambda state: WorkflowService._execute_fork_node(node, state))
            elif node.type == "join":
                # Add join node
                graph.add_node(node.name, lambda state: WorkflowService._execute_join_node(node, state))
            elif node.type == "iteration":
                # Add iteration node
                graph.add_node(node.name, lambda state: WorkflowService._execute_iteration_node(node, state))
            elif node.type == "code":
                # Add code execution node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_code_node(node, state))
            elif node.type == "template":
                # Add template node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_template_node(node, state))
            elif node.type == "variable_aggregator":
                # Add variable aggregator node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_variable_aggregator_node(node, state))
            elif node.type == "document_extractor":
                # Add document extractor node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_document_extractor_node(node, state))
            elif node.type == "variable_assigner":
                # Add variable assigner node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_variable_assigner_node(node, state))
            elif node.type == "parameter_extractor":
                # Add parameter extractor node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_parameter_extractor_node(node, state))
            elif node.type == "http":
                # Add HTTP request node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_http_node(node, state))
            elif node.type == "list_operation":
                # Add list operation node (Dify style)
                graph.add_node(node.name, lambda state: WorkflowService._execute_list_operation_node(node, state))
        
        # Add edges to the graph
        for edge in workflow.edges:
            source_node = await edge.source_node
            target_node = await edge.target_node
            if edge.condition:
                # Add conditional edge
                graph.add_conditional_edges(
                    source_node.name,
                    lambda state: WorkflowService._evaluate_condition(edge.condition, state),
                    {target_node.name: target_node.name}
                )
            else:
                # Add unconditional edge
                graph.add_edge(source_node.name, target_node.name)
        
        # Set entry point
        entry_node = next((node for node in workflow.nodes if node.position.get('x') < 100), None)
        if entry_node:
            graph.set_entry_point(entry_node.name)
        
        # Compile the graph
        compiled_graph = graph.compile()
        
        # Execute the graph
        result = await compiled_graph.ainvoke(input_data)
        
        return result

    @staticmethod
    async def _execute_agent_node(agent: Agent, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent node"""
        # Here you would implement the agent execution logic
        # This could involve calling the agent's API or using LangChain
        print(f"Executing agent: {agent.name}")
        
        # Simulate agent execution
        state[f"agent_{agent.id}_output"] = f"Output from agent {agent.name}"
        return state

    @staticmethod
    async def _execute_skill_node(skill: Skill, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute skill node"""
        # Here you would implement the skill execution logic
        # This could involve running the skill's implementation code
        print(f"Executing skill: {skill.name}")
        
        # Simulate skill execution
        state[f"skill_{skill.id}_output"] = f"Output from skill {skill.name}"
        return state

    @staticmethod
    async def _execute_decision_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute decision node"""
        # Here you would implement the decision logic
        print(f"Executing decision node: {node.name}")
        
        # Simulate decision
        state[f"decision_{node.id}_output"] = "Decision made"
        return state

    @staticmethod
    async def _execute_fork_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute fork node"""
        # Here you would implement the fork logic
        print(f"Executing fork node: {node.name}")
        
        # Simulate fork
        state[f"fork_{node.id}_output"] = "Fork executed"
        return state

    @staticmethod
    async def _execute_join_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute join node"""
        # Here you would implement the join logic
        print(f"Executing join node: {node.name}")
        
        # Simulate join
        state[f"join_{node.id}_output"] = "Join executed"
        return state

    @staticmethod
    async def _execute_iteration_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute iteration node"""
        print(f"Executing iteration node: {node.name}")
        
        # Get iteration configuration
        config = node.config or {}
        iteration_collection = config.get('iteration_collection', '')
        iteration_variable = config.get('iteration_variable', 'item')
        iteration_condition = config.get('iteration_condition', '')
        
        # Get the collection from state
        collection = state.get(iteration_collection, [])
        
        # Execute iteration
        results = []
        for item in collection:
            # Set the iteration variable in state
            state[iteration_variable] = item
            
            # Evaluate condition if provided
            if iteration_condition:
                from base.plugins.agent.utils.safe_eval import safe_eval_condition
                try:
                    condition_result = safe_eval_condition(iteration_condition, state)
                    if not condition_result:
                        continue
                except Exception as e:
                    print(f"Error evaluating iteration condition: {e}")
                    continue
            
            # Add item to results
            results.append(item)
        
        # Store results in state
        state[f"iteration_{node.id}_output"] = results
        state[f"iteration_{node.id}_collection"] = collection
        state[f"iteration_{node.id}_count"] = len(results)
        
        return state

    @staticmethod
    async def _evaluate_condition(condition: str, state: Dict[str, Any]) -> str:
        """Evaluate condition"""
        # Here you would implement condition evaluation
        # This could involve evaluating the condition against the state
        print(f"Evaluating condition: {condition}")
        
        # Simulate condition evaluation
        return "true"
    
    # ==================== Dify 风格节点执行函数 ====================
    
    @staticmethod
    async def _execute_llm_node(llm: LLMModel, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute LLM node"""
        print(f"Executing LLM node: {llm.model_name}")
        
        # Get LLM configuration from node config
        config = llm.config or {}
        prompt = config.get('prompt', '')
        temperature = config.get('temperature', 0.7)
        max_tokens = config.get('max_tokens', 2048)
        
        # Simulate LLM execution
        # In production, this would call the actual LLM API
        state[f"llm_{llm.id}_output"] = {
            "model": llm.model_name,
            "prompt": prompt,
            "response": f"Simulated response from {llm.model_name}",
            "temperature": temperature
        }
        return state
    
    @staticmethod
    async def _execute_code_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code node (Dify style)"""
        print(f"Executing code node: {node.name}")
        
        # Get code configuration
        config = node.config or {}
        language = config.get('language', 'python')
        code = config.get('code', '')
        
        # Execute code
        try:
            if language == 'python':
                # Execute Python code
                exec_globals = {'state': state, 'json': json, 're': re}
                exec(code, exec_globals)
                result = exec_globals.get('result', 'Code executed successfully')
            elif language == 'javascript':
                # Execute JavaScript code (simplified)
                result = f"JavaScript code executed: {code[:50]}..."
            else:
                result = f"Unsupported language: {language}"
        except Exception as e:
            result = f"Code execution error: {str(e)}"
        
        state[f"code_{node.id}_output"] = result
        return state
    
    @staticmethod
    async def _execute_template_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute template node (Dify style)"""
        print(f"Executing template node: {node.name}")
        
        # Get template configuration
        config = node.config or {}
        template = config.get('template', '')
        
        # Render template
        try:
            # Simple template rendering (in production, use Jinja2 or similar)
            rendered = template
            for key, value in state.items():
                if isinstance(value, (str, int, float, bool)):
                    rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        except Exception as e:
            rendered = f"Template rendering error: {str(e)}"
        
        state[f"template_{node.id}_output"] = rendered
        return state
    
    @staticmethod
    async def _execute_variable_aggregator_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute variable aggregator node (Dify style)"""
        print(f"Executing variable aggregator node: {node.name}")
        
        # Get configuration
        config = node.config or {}
        input_vars = config.get('input_vars', '').split('\n')
        output_var = config.get('output_var', 'aggregated_output')
        
        # Aggregate variables
        aggregated = {}
        for var_name in input_vars:
            var_name = var_name.strip()
            if var_name in state:
                aggregated[var_name] = state[var_name]
        
        state[output_var] = aggregated
        state[f"variable_aggregator_{node.id}_output"] = aggregated
        return state
    
    @staticmethod
    async def _execute_document_extractor_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute document extractor node (Dify style)"""
        print(f"Executing document extractor node: {node.name}")
        
        # Get configuration
        config = node.config or {}
        document_var = config.get('document_var', '')
        extract_rules = config.get('extract_rules', '')
        
        # Extract content from document
        # In production, this would use actual document processing
        extracted = {
            "document_var": document_var,
            "extract_rules": extract_rules,
            "extracted_content": f"Extracted content from {document_var}"
        }
        
        state[f"document_extractor_{node.id}_output"] = extracted
        return state
    
    @staticmethod
    async def _execute_variable_assigner_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute variable assigner node (Dify style)"""
        print(f"Executing variable assigner node: {node.name}")
        
        # Get configuration
        config = node.config or {}
        var_name = config.get('var_name', '')
        var_value = config.get('var_value', '')
        
        # Assign variable
        state[var_name] = var_value
        state[f"variable_assigner_{node.id}_output"] = f"Variable {var_name} assigned"
        return state
    
    @staticmethod
    async def _execute_parameter_extractor_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute parameter extractor node (Dify style)"""
        print(f"Executing parameter extractor node: {node.name}")
        
        # Get configuration
        config = node.config or {}
        input_text = config.get('input_text', '')
        parameters = config.get('parameters', '').split('\n')
        
        # Extract parameters
        extracted_params = {}
        for param_name in parameters:
            param_name = param_name.strip()
            # In production, this would use actual parameter extraction logic
            extracted_params[param_name] = f"Extracted {param_name}"
        
        state[f"parameter_extractor_{node.id}_output"] = extracted_params
        return state
    
    @staticmethod
    async def _execute_http_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP request node (Dify style)"""
        print(f"Executing HTTP node: {node.name}")
        
        # Get configuration
        config = node.config or {}
        method = config.get('method', 'GET')
        url = config.get('url', '')
        headers = config.get('headers', '{}')
        body = config.get('body', '{}')
        
        # Execute HTTP request
        if HTTPX_AVAILABLE:
            try:
                async with httpx.AsyncClient() as client:
                    if method == 'GET':
                        response = await client.get(url, headers=json.loads(headers))
                    elif method == 'POST':
                        response = await client.post(url, headers=json.loads(headers), json=json.loads(body))
                    elif method == 'PUT':
                        response = await client.put(url, headers=json.loads(headers), json=json.loads(body))
                    elif method == 'DELETE':
                        response = await client.delete(url, headers=json.loads(headers))
                    else:
                        response = None
                    
                    result = {
                        "status_code": response.status_code if response else 0,
                        "response": response.text if response else "No response",
                        "headers": dict(response.headers) if response else {}
                    }
            except Exception as e:
                result = {
                    "error": str(e),
                    "status_code": 0
                }
        else:
            # Fallback if httpx is not available
            result = {
                "message": "HTTPX library not available",
                "url": url,
                "method": method,
                "simulated_response": "HTTP request would be executed here"
            }
        
        state[f"http_{node.id}_output"] = result
        return state
    
    @staticmethod
    async def _execute_list_operation_node(node: WorkflowNode, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute list operation node (Dify style)"""
        print(f"Executing list operation node: {node.name}")
        
        # Get configuration
        config = node.config or {}
        operation = config.get('operation', 'filter')
        input_list = config.get('input_list', '')
        
        # Get the list from state
        input_data = state.get(input_list, [])
        
        # Perform operation
        if operation == 'filter':
            result = [item for item in input_data if item]  # Simple filter
        elif operation == 'map':
            result = [f"Processed: {item}" for item in input_data]  # Simple map
        elif operation == 'sort':
            result = sorted(input_data)  # Simple sort
        elif operation == 'unique':
            result = list(set(input_data))  # Remove duplicates
        else:
            result = input_data
        
        state[f"list_operation_{node.id}_output"] = result
        return state

    @staticmethod
    def should_use_sse(workflow) -> bool:
        """
        判断工作流是否应该使用 SSE 模式执行

        判断条件：
        1. 有流式 LLM 节点（stream=True）
        2. 有工具/HTTP/技能节点（可能需要等待外部响应）
        3. 有条件分支或循环节点（需要多轮执行）

        Args:
            workflow: 工作流对象

        Returns:
            是否应该使用 SSE 模式
        """
        graph = workflow.definition
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
        agent,
        input_data: Dict[str, Any],
        execution_id: str,
        execution_manager: dict,
        actor: dict
    ):
        """
        SSE事件生成器 - 实时推送执行过程（支持边思考边输出）

        Args:
            agent: 模拟的agent对象（包含graph_definition）
            input_data: 输入数据
            execution_id: 执行ID
            execution_manager: 执行管理器（用于检查取消状态）
            actor: 当前用户

        Returns:
            SSE事件流
        """
        from base.plugins.agent.services.langgraph_executor import LangGraphExecutor
        import json
        from datetime import datetime

        logger = logging.getLogger(__name__)
        logger.info(f"[Workflow Execution] 开始执行，execution_id: {execution_id}")

        def send_event(event_data):
            return f"data: {json.dumps({**event_data, 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

        async def check_cancelled():
            exec_info = execution_manager.get(execution_id)
            return exec_info and exec_info.get('is_cancelled', False)

        try:
            yield send_event({'type': 'start', 'execution_id': execution_id, 'message': '开始执行工作流'})

            class SSEQueue:
                def __init__(self):
                    self.queue = asyncio.Queue()

                async def put(self, event):
                    await self.queue.put(event)

                async def get(self):
                    return await self.queue.get()

                def empty(self):
                    return self.queue.empty()

            sse_queue = SSEQueue()
            sse_yield_call_count = [0]

            async def wrapped_sse_yield_with_counter(event):
                sse_yield_call_count[0] += 1
                await sse_queue.put(event)

            async def execute_task():
                logger.info(f"[Workflow SSE生成器] execute_task 开始执行")
                try:
                    exec_info = execution_manager.get(execution_id, {})
                    llm_resources = exec_info.get('_llm_resources', {})
                    skill_resources = exec_info.get('_skill_resources', {})
                    logger.info(f"[Workflow SSE生成器] 获取预加载资源: LLM={len(llm_resources)}, 技能={len(skill_resources)}")

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
                    logger.error(f"[Workflow SSE生成器] LangGraph 执行异常: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return {
                        "success": False,
                        "message": str(e),
                        "traceback": traceback.format_exc()
                    }

            task = asyncio.create_task(execute_task())

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
                        logger.info("[Workflow Execution] 任务已完成，队列已空，退出循环")

                except Exception as e:
                    logger.error(f"[Workflow SSE 推送异常] {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    break

            logger.info("[Workflow Execution] while循环已退出，准备获取task结果")
            try:
                logger.info(f"[Workflow Execution] 检查task状态: cancelled={task.cancelled()}, done={task.done()}")
                if not task.cancelled():
                    result = await task
                    logger.info(f"[Workflow Execution] await task 完成，result.success={result.get('success')}")

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

                    logger.info("[Workflow Execution] 准备发送 complete 事件")
                    yield send_event({
                        'type': 'complete',
                        'result': result.get('output', {}),
                        'variables': variables_summary
                    })
                    logger.info("[Workflow Execution] complete 事件已发送")
                else:
                    logger.warning("[Workflow Execution] task已被取消，跳过获取结果")
            except Exception as e:
                logger.error(f"获取执行结果失败: {e}")
                yield send_event({'type': 'error', 'message': str(e)})

        except Exception as e:
            import traceback
            yield send_event({'type': 'error', 'message': str(e), 'traceback': traceback.format_exc()})

    @staticmethod
    async def execute_workflow_direct(workflow_id: int, input_data: dict, actor: dict, execution_id: str = None) -> dict:
        """
        直接执行工作流（非SSE模式）

        Args:
            workflow_id: 工作流ID
            input_data: 输入数据
            actor: 当前用户
            execution_id: 执行ID

        Returns:
            执行结果
        """
        workflow = await WorkflowService.get_workflow_by_id(workflow_id)
        if not workflow or workflow.status != "active":
            return {"success": False, "message": "Workflow not found or inactive"}

        try:
            from base.plugins.agent.services.langgraph_executor import LangGraphExecutor

            class MockAgent:
                def __init__(self, definition, wid, wname):
                    self.graph_definition = definition
                    self.id = wid
                    self.name = wname

            mock_agent = MockAgent(workflow.definition or {}, workflow_id, workflow.name)
            result = await LangGraphExecutor.execute_agent(
                agent=mock_agent,
                input_data=input_data,
                actor=actor,
                execution_id=execution_id
            )
            return result

        except Exception as e:
            import traceback
            return {"success": False, "message": str(e), "traceback": traceback.format_exc()}

    # ==================== M3 工作流定义与版本（T5，Schema v2） ====================

    @staticmethod
    def empty_v2_graph(name: str = "") -> Dict[str, Any]:
        """空白 Schema v2 图（最小可发布骨架：start → end）"""
        return {
            "schema_version": 2,
            "meta": {"name": name},
            "variables": [
                {"name": "query", "type": "string", "required": True, "source": "user_input"},
            ],
            "nodes": [
                {"id": "n_start", "type": "start", "position": {"x": 80, "y": 200},
                 "data": {"label": "开始", "config": {},
                          "outputs": [{"name": "query", "type": "string"}]}},
                {"id": "n_end", "type": "end", "position": {"x": 480, "y": 200},
                 "data": {"label": "结束", "config": {"output_mode": "last"},
                          "inputs": [{"name": "answer", "type": "any", "from": "n_start.query"}],
                          "outputs": []}},
            ],
            "edges": [
                {"id": "e1", "source": "n_start", "sourceHandle": "query",
                 "target": "n_end", "targetHandle": "answer"},
            ],
            "settings": {"timeout_s": 300, "retry": {"max": 3, "backoff": "1,2,4"},
                         "trace_level": "standard", "memory_mode": "private"},
        }

    @staticmethod
    async def _resource_checker_for(owner: OwnerContext, domain: str):
        """资源授权批量判定注入（仅用户域；后台域保持既有行为不做授权拦截）"""
        if domain != DOMAIN_USER:
            return None

        async def _check(resource_type: str, ids: List[str]):
            return await ResourceGrantService.check_many(
                (owner.owner_type, owner.owner_id), resource_type, ids
            )

        return _check

    @staticmethod
    async def _subworkflow_checker_for(owner: OwnerContext):
        """子工作流引用有效性判定注入（E-108）：存在、可见、已发布、锁定版本有效"""

        async def _check(wf_ref: str, pinned: Optional[int]) -> Optional[str]:
            try:
                wid = int(wf_ref)
            except (TypeError, ValueError):
                return f"子工作流标识非法: {wf_ref}"
            sub = await Workflow.filter(id=wid).first()
            if sub is None:
                return f"子工作流 {wf_ref} 不存在或已删除"
            if not is_accessible(sub, owner, include_public=True):
                return f"子工作流 {wf_ref} 不可见"
            if sub.current_version_id is None:
                return f"子工作流 {wf_ref} 未发布"
            if pinned is not None:
                try:
                    pv = int(pinned)
                except (TypeError, ValueError):
                    return f"子工作流 {wf_ref} 锁定版本号非法"
                exists = await WorkflowVersion.filter(
                    workflow_id=wid, version_no=pv, status="published"
                ).exists()
                if not exists:
                    return f"子工作流 {wf_ref} 版本 v{pv} 失效或已删除"
            return None

        return _check

    @classmethod
    async def validate_graph_for(cls, owner: OwnerContext, graph_json: Dict[str, Any],
                                 domain: str = DOMAIN_USER) -> List[Dict[str, Any]]:
        """全量校验入口（R-03）：结构 + 资源授权（用户域）+ 子工作流引用"""
        return await validate_graph(
            graph_json,
            domain=domain,
            resource_checker=await cls._resource_checker_for(owner, domain),
            subworkflow_checker=await cls._subworkflow_checker_for(owner),
        )

    @classmethod
    async def create_user_workflow(cls, owner: OwnerContext, name: str,
                                   description: str = "",
                                   graph_json: Optional[Dict[str, Any]] = None,
                                   template_id: Optional[int] = None):
        """
        用户侧新建（空白/模板，04-§2.1 POST /v1/u/workflows）
        模板复制：归属当前主体，模板本身只读（PRD §6.4-B6）
        """
        graph = graph_json
        if graph is None and template_id is not None:
            tpl = await Workflow.filter(id=template_id).first()
            if tpl is None or tpl.visibility not in ("template", "public"):
                from base.common.authz import OwnedResourceNotFound
                raise OwnedResourceNotFound("模板不存在")
            if tpl.current_version_id is not None:
                ver = await WorkflowVersion.filter(id=tpl.current_version_id).first()
                graph = ver.graph_json if ver is not None else None
            if graph is None:
                graph = tpl.definition
        if graph is None:
            graph = cls.empty_v2_graph(name)
        issues = await cls.validate_graph_for(owner, graph, DOMAIN_USER)
        workflow = await Workflow.create(
            name=name, description=description or "", status="draft",
            definition=graph, owner_type=owner.owner_type, owner_id=owner.owner_id,
            visibility="private", schema_version="v2",
        )
        return workflow, issues

    @classmethod
    async def save_draft(cls, workflow_id: int, graph_json: Dict[str, Any],
                         draft_version: int, owner: OwnerContext,
                         domain: str = DOMAIN_USER):
        """
        保存草稿（04-F1）：
        - 乐观锁 draft_version：条件更新 0 行即 409 冲突
        - 保存时服务端全量校验（错误不阻断保存，随响应返回校验结果）
        Returns: (workflow, issues)
        """
        wf = await get_owned_or_404(Workflow, workflow_id, owner, for_write=True)
        issues = await cls.validate_graph_for(owner, graph_json, domain)
        rows = await Workflow.filter(
            id=wf.id, draft_version=int(draft_version)
        ).update(
            definition=graph_json,
            schema_version="v2",
            draft_version=int(draft_version) + 1,
        )
        if rows == 0:
            current = await Workflow.filter(id=wf.id).values_list("draft_version", flat=True)
            raise DraftConflictError(current[0] if current else 0)
        fresh = await Workflow.get(id=wf.id)
        return fresh, issues

    @classmethod
    async def publish_workflow(cls, workflow_id: int, owner: OwnerContext,
                               idempotency_key: Optional[str] = None,
                               domain: str = DOMAIN_USER,
                               description: str = "") -> Dict[str, Any]:
        """
        发布（04-F1）：
        Idempotency-Key 24h 去重（重放返回原响应）→ 全量校验（错误阻断）→
        生成不可变 workflow_version（version_no 自增 + 资源快照 ID 清单）→ 更新 current_version_id
        """
        idem_key = (
            f"publish:{owner.owner_type}:{owner.owner_id}:{workflow_id}:{idempotency_key}"
            if idempotency_key else None
        )
        if idem_key:
            hit = await _IdempotencyStore.get(idem_key)
            if hit is not None:
                return {**hit, "idempotent_replay": True}

        wf = await get_owned_or_404(Workflow, workflow_id, owner, for_write=True)
        graph = wf.definition or {}
        issues = await cls.validate_graph_for(owner, graph, domain)
        if has_blocking_errors(issues):
            raise ValidationBlockedError(issues)

        async with in_transaction():
            agg = await WorkflowVersion.filter(workflow_id=wf.id).annotate(
                m=Max("version_no")
            ).values("m")
            next_no = ((agg[0]["m"] or 0) + 1) if agg else 1
            version = await WorkflowVersion.create(
                workflow_id=wf.id,
                version_no=next_no,
                graph_json=graph,
                schema_version="v2",
                resource_refs=collect_resource_refs(graph),
                published_by_type=owner.owner_type,
                published_by_id=owner.owner_id,
                published_at=datetime.now(),
                status="published",
                # BUG-T15-004：openGauss 空串即 NULL，写库前归一化（空→None 而非 ""）
                description=description if description else None,
            )
            await Workflow.filter(id=wf.id).update(
                current_version_id=version.id, status="active", schema_version="v2"
            )

        payload = {
            "version_id": version.id,
            "version_no": version.version_no,
            "published_at": version.published_at.isoformat() if version.published_at else None,
        }
        if idem_key:
            await _IdempotencyStore.set(idem_key, payload)
        return payload

    @classmethod
    async def list_versions(cls, workflow_id: int, owner: OwnerContext) -> List[WorkflowVersion]:
        """版本列表（只读；公开/模板可见性可读）"""
        wf = await get_owned_or_404(Workflow, workflow_id, owner, include_public=True)
        return await WorkflowVersion.filter(workflow_id=wf.id).order_by("-version_no")

    @staticmethod
    def validation_summary(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """校验结果摘要包装（错误不阻断保存时随响应返回，04-F1）"""
        errors = [i for i in issues if i.get("level") == "error"]
        warnings = [i for i in issues if i.get("level") == "warning"]
        return {
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "issues": issues,
        }

    @classmethod
    async def get_version_snapshot(cls, workflow_id: int, version_no: int,
                                   owner: OwnerContext) -> WorkflowVersion:
        """版本快照（只读，按 version_no 定位）"""
        from base.common.authz import OwnedResourceNotFound
        wf = await get_owned_or_404(Workflow, workflow_id, owner, include_public=True)
        version = await WorkflowVersion.filter(
            workflow_id=wf.id, version_no=int(version_no)
        ).first()
        if version is None:
            raise OwnedResourceNotFound("版本不存在")
        return version

    @classmethod
    async def rollback_workflow(cls, workflow_id: int, version_no: int,
                                owner: OwnerContext, domain: str = DOMAIN_USER) -> Dict[str, Any]:
        """
        回滚（04-§2.1）：以旧版本 graph_json 生成新版本（旧版本本身不可变不动）
        新图需过全量校验（旧版本引用资源可能已失效，失效即 E-108/E-110 阻断）
        """
        from base.common.authz import OwnedResourceNotFound
        wf = await get_owned_or_404(Workflow, workflow_id, owner, for_write=True)
        src = await WorkflowVersion.filter(
            workflow_id=wf.id, version_no=int(version_no)
        ).first()
        if src is None:
            raise OwnedResourceNotFound("目标版本不存在")

        issues = await cls.validate_graph_for(owner, src.graph_json, domain)
        if has_blocking_errors(issues):
            raise ValidationBlockedError(issues)

        async with in_transaction():
            agg = await WorkflowVersion.filter(workflow_id=wf.id).annotate(
                m=Max("version_no")
            ).values("m")
            next_no = ((agg[0]["m"] or 0) + 1) if agg else 1
            version = await WorkflowVersion.create(
                workflow_id=wf.id,
                version_no=next_no,
                graph_json=src.graph_json,
                schema_version=src.schema_version or "v2",
                resource_refs=src.resource_refs,
                published_by_type=owner.owner_type,
                published_by_id=owner.owner_id,
                published_at=datetime.now(),
                status="published",
            )
            await Workflow.filter(id=wf.id).update(
                current_version_id=version.id,
                status="active",
                schema_version=version.schema_version,
            )
        return {
            "version_id": version.id,
            "version_no": version.version_no,
            "rolled_back_from": src.version_no,
            "published_at": version.published_at.isoformat() if version.published_at else None,
        }

    @classmethod
    async def disable_workflow(cls, workflow_id: int, owner: OwnerContext) -> Workflow:
        """停用（publish_status 流转 active → inactive，PRD §6.4-B5）"""
        wf = await get_owned_or_404(Workflow, workflow_id, owner, for_write=True)
        await Workflow.filter(id=wf.id).update(status="inactive")
        return await Workflow.get(id=wf.id)

    @classmethod
    async def validate_user_workflow(
        cls,
        workflow_id: int,
        graph_json: Dict[str, Any],
        *,
        owner: OwnerContext,
    ) -> Dict[str, Any]:
        """用户侧校验端点：归属校验 + user 域全量校验（返回摘要结构）"""
        await get_owned_or_404(Workflow, workflow_id, owner, include_public=True)
        issues = await cls.validate_graph_for(owner, graph_json, domain=DOMAIN_USER)
        return cls.validation_summary(issues)

    @classmethod
    async def get_user_workflow_detail(
        cls,
        workflow_id: int,
        *,
        owner: OwnerContext,
    ) -> Dict[str, Any]:
        """用户侧详情：归属过滤 + 草稿校验结果（PRD §7.3 问题面板数据源）"""
        workflow = await get_owned_or_404(
            Workflow, workflow_id, owner, include_public=True
        )
        definition = workflow.definition or {}
        if definition:
            validation = cls.validation_summary(
                await cls.validate_graph_for(owner, definition, domain=DOMAIN_USER)
            )
        else:
            validation = {"valid": True, "error_count": 0, "warning_count": 0, "issues": []}
        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status,
            "schema_version": workflow.schema_version,
            "draft_version": workflow.draft_version,
            "current_version_id": workflow.current_version_id,
            "definition": definition,
            "validation": validation,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        }
