"""
任务拆解智能体服务
专门负责将复杂任务拆解成可执行子任务
"""
import asyncio
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
logger = logging.getLogger(__name__)

try:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import PydanticOutputParser
    from pydantic import BaseModel, Field
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class SubTask(BaseModel):
    """子任务模型"""
    id: str = Field(description="子任务ID")
    name: str = Field(description="子任务名称")
    description: str = Field(description="子任务描述")
    dependencies: List[str] = Field(default=[], description="依赖的子任务ID列表")
    tool: str = Field(default="", description="需要使用的工具")


class TaskPlan(BaseModel):
    """任务计划模型"""
    original_task: str = Field(description="原始任务")
    subtasks: List[SubTask] = Field(description="子任务列表")
    reasoning: str = Field(description="拆解理由")


class TaskDecomposerService:
    model = "task_decomposer"
    """
    任务拆解智能体服务
    """
    
    @staticmethod
    def create_decomposition_prompt() -> ChatPromptTemplate:
        """
        创建任务拆解提示词模板
        
        Returns:
            ChatPromptTemplate
        """
        if not LANGCHAIN_AVAILABLE:
            return None
        
        template = """你是一个专业的任务拆解专家，擅长将复杂任务拆解成可执行的子任务。

请分析用户的任务，将其拆解成 3-7 个子任务。

要求：
1. 每个子任务应该是可独立执行的
2. 子任务之间应该有合理的依赖关系
3. 每个子任务应该明确需要使用什么工具（如果需要）
4. 子任务的顺序应该合理

可用工具：
- translation: 翻译工具
- search: 搜索工具
- calculator: 计算工具
- database: 数据库查询工具
- api: API 调用工具
- writer: 写作工具
- none: 不需要工具

用户任务：{task}

请以 JSON 格式输出，格式如下：
{{
    "original_task": "原始任务",
    "subtasks": [
        {{
            "id": "1",
            "name": "子任务名称",
            "description": "子任务描述",
            "dependencies": [],
            "tool": "工具名称"
        }}
    ],
    "reasoning": "拆解理由"
}}
"""
        return ChatPromptTemplate.from_template(template)
    
    @staticmethod
    async def decompose_task(
        task: str,
        model_name: str = "gpt-3.5-turbo"
    ) -> Dict[str, Any]:
        """
        拆解任务
        
        Args:
            task: 原始任务
            model_name: 大模型名称
            
        Returns:
            拆解结果
        """
        logger.info(f"开始拆解任务: {task}")
        
        if not LANGCHAIN_AVAILABLE:
            logger.warning("LangChain 不可用，使用简化拆解方式")
            return TaskDecomposerService._decompose_simple(task)
        
        try:
            from langchain_openai import ChatOpenAI
            
            # 创建提示词
            prompt = TaskDecomposerService.create_decomposition_prompt()
            
            # 创建模型
            model = ChatOpenAI(model=model_name, temperature=0)
            
            # 创建输出解析器
            parser = PydanticOutputParser(pydantic_object=TaskPlan)
            
            # 创建链
            chain = prompt | model | parser
            
            # 执行拆解
            result = await chain.ainvoke({"task": task})
            
            logger.info(f"任务拆解成功: {len(result.subtasks)} 个子任务")
            
            return {
                "success": True,
                "plan": result.model_dump(),
                "subtask_count": len(result.subtasks)
            }
            
        except Exception as e:
            logger.error(f"任务拆解失败: {e}")
            logger.warning("使用简化拆解方式")
            return TaskDecomposerService._decompose_simple(task)
    
    @staticmethod
    def _decompose_simple(task: str) -> Dict[str, Any]:
        """
        简化的任务拆解方式（不使用 LLM）
        
        Args:
            task: 原始任务
            
        Returns:
            拆解结果
        """
        # 基于关键词的简单拆解
        subtasks = []
        
        # 分析任务内容
        task_lower = task.lower()
        
        # 根据关键词生成子任务
        if "翻译" in task_lower or "translate" in task_lower:
            subtasks.append({
                "id": "1",
                "name": "理解原文",
                "description": "理解需要翻译的内容",
                "dependencies": [],
                "tool": "none"
            })
            subtasks.append({
                "id": "2",
                "name": "执行翻译",
                "description": "使用翻译工具进行翻译",
                "dependencies": ["1"],
                "tool": "translation"
            })
            subtasks.append({
                "id": "3",
                "name": "校对结果",
                "description": "检查翻译结果的准确性",
                "dependencies": ["2"],
                "tool": "none"
            })
        elif "搜索" in task_lower or "search" in task_lower:
            subtasks.append({
                "id": "1",
                "name": "确定关键词",
                "description": "确定搜索关键词",
                "dependencies": [],
                "tool": "none"
            })
            subtasks.append({
                "id": "2",
                "name": "执行搜索",
                "description": "使用搜索工具查找信息",
                "dependencies": ["1"],
                "tool": "search"
            })
            subtasks.append({
                "id": "3",
                "name": "整理结果",
                "description": "整理和总结搜索结果",
                "dependencies": ["2"],
                "tool": "writer"
            })
        elif "写" in task_lower or "write" in task_lower or "创作" in task_lower:
            subtasks.append({
                "id": "1",
                "name": "理解需求",
                "description": "理解写作需求和目标",
                "dependencies": [],
                "tool": "none"
            })
            subtasks.append({
                "id": "2",
                "name": "收集资料",
                "description": "收集相关资料和信息",
                "dependencies": ["1"],
                "tool": "search"
            })
            subtasks.append({
                "id": "3",
                "name": "撰写内容",
                "description": "开始撰写内容",
                "dependencies": ["2"],
                "tool": "writer"
            })
            subtasks.append({
                "id": "4",
                "name": "校对修改",
                "description": "校对和修改内容",
                "dependencies": ["3"],
                "tool": "none"
            })
        else:
            # 默认拆解
            subtasks.append({
                "id": "1",
                "name": "分析任务",
                "description": "分析任务要求",
                "dependencies": [],
                "tool": "none"
            })
            subtasks.append({
                "id": "2",
                "name": "执行任务",
                "description": "执行主要任务",
                "dependencies": ["1"],
                "tool": "none"
            })
            subtasks.append({
                "id": "3",
                "name": "验证结果",
                "description": "验证任务结果",
                "dependencies": ["2"],
                "tool": "none"
            })
        
        return {
            "success": True,
            "plan": {
                "original_task": task,
                "subtasks": subtasks,
                "reasoning": "基于关键词的简化拆解"
            },
            "subtask_count": len(subtasks),
            "note": "使用简化拆解方式，建议安装 LangChain 以获得更好效果"
        }
    
    @staticmethod
    async def execute_plan(
        plan: Dict[str, Any],
        executor: Any = None
    ) -> Dict[str, Any]:
        """
        执行任务计划
        
        Args:
            plan: 任务计划
            executor: 执行器（可选）
            
        Returns:
            执行结果
        """
        logger.info("开始执行任务计划")
        
        subtasks = plan.get("subtasks", [])
        results = {}
        execution_order = []
        
        try:
            # 按依赖关系排序
            execution_order = TaskDecomposerService._sort_subtasks(subtasks)
            
            # 执行子任务
            for subtask_id in execution_order:
                subtask = next((t for t in subtasks if t["id"] == subtask_id), None)
                if not subtask:
                    continue
                
                logger.info(f"执行子任务: {subtask['name']}")
                
                # 收集依赖结果
                dependency_results = {}
                for dep_id in subtask.get("dependencies", []):
                    if dep_id in results:
                        dependency_results[dep_id] = results[dep_id]
                
                # 执行子任务（这里简化处理，实际应该调用对应的工具）
                result = await TaskDecomposerService._execute_subtask(
                    subtask, 
                    dependency_results,
                    executor
                )
                
                results[subtask_id] = result
                logger.info(f"子任务完成: {subtask['name']}")
            
            logger.info("任务计划执行完成")
            
            return {
                "success": True,
                "results": results,
                "execution_order": execution_order,
                "completed_count": len(results)
            }
            
        except Exception as e:
            logger.error(f"执行任务计划失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "results": results,
                "execution_order": execution_order
            }
    
    @staticmethod
    def _sort_subtasks(subtasks: List[Dict]) -> List[str]:
        """
        按依赖关系排序子任务
        
        Args:
            subtasks: 子任务列表
            
        Returns:
            排序后的子任务ID列表
        """
        # 简单的拓扑排序
        result = []
        visited = set()
        temp = set()
        
        def visit(node_id):
            if node_id in temp:
                raise ValueError("循环依赖")
            if node_id in visited:
                return
            
            temp.add(node_id)
            
            # 找到这个节点
            node = next((t for t in subtasks if t["id"] == node_id), None)
            if node:
                for dep in node.get("dependencies", []):
                    visit(dep)
            
            temp.remove(node_id)
            visited.add(node_id)
            result.append(node_id)
        
        for subtask in subtasks:
            if subtask["id"] not in visited:
                visit(subtask["id"])
        
        return result
    
    @staticmethod
    async def _execute_subtask(
        subtask: Dict,
        dependency_results: Dict,
        executor: Any
    ) -> Dict[str, Any]:
        """
        执行单个子任务
        
        Args:
            subtask: 子任务
            dependency_results: 依赖结果
            executor: 执行器
            
        Returns:
            执行结果
        """
        # 这里只是模拟执行
        await asyncio.sleep(0.1)
        
        return {
            "success": True,
            "subtask": subtask["name"],
            "result": f"执行完成: {subtask['name']}",
            "dependency_results": dependency_results,
            "timestamp": datetime.now().isoformat()
        }


class PlanAndExecuteAgent:
    """
    Plan-and-Execute 智能体
    先规划，再执行
    """
    
    @staticmethod
    async def run(
        task: str,
        model_name: str = "gpt-3.5-turbo"
    ) -> Dict[str, Any]:
        """
        运行 Plan-and-Execute 智能体
        
        Args:
            task: 任务
            model_name: 模型名称
            
        Returns:
            执行结果
        """
        logger.info(f"Plan-and-Execute 智能体开始执行: {task}")
        
        # 阶段 1: 规划
        plan_result = await TaskDecomposerService.decompose_task(task, model_name)
        
        if not plan_result.get("success"):
            return plan_result
        
        # 阶段 2: 执行
        plan = plan_result.get("plan", {})
        execute_result = await TaskDecomposerService.execute_plan(plan)
        
        return {
            "success": True,
            "task": task,
            "plan": plan,
            "execution": execute_result
        }
