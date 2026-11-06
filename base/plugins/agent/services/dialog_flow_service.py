from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
import json
import logging
from base.plugins.agent.models.dialog_flow import DialogFlow, DialogFlowNode, DialogFlowEdge, DialogFlowExecution
from base.plugins.agent.schemas.dialog_flow import (
    DialogFlowCreate, DialogFlowUpdate, DialogFlowResponse,
    DialogFlowNodeCreate, DialogFlowNodeUpdate, DialogFlowNodeResponse,
    DialogFlowEdgeCreate, DialogFlowEdgeUpdate, DialogFlowEdgeResponse,
    DialogFlowExecutionCreate, DialogFlowExecutionResponse
)

logger = logging.getLogger(__name__)


class DialogFlowService:
    model = "dialog_flow"
    """对话流服务"""
    
    @staticmethod
    async def create_dialog_flow(data: DialogFlowCreate) -> DialogFlowResponse:
        """创建对话流"""
        dialog_flow = await DialogFlow.create(**data.dict())
        return DialogFlowResponse.from_orm(dialog_flow)
    
    @staticmethod
    async def get_dialog_flow(dialog_flow_id: int) -> Optional[DialogFlowResponse]:
        """获取对话流"""
        dialog_flow = await DialogFlow.get_or_none(id=dialog_flow_id)
        if not dialog_flow:
            return None
        return DialogFlowResponse.from_orm(dialog_flow)
    
    @staticmethod
    async def list_dialog_flows(agent_id: Optional[int] = None, skip: int = 0, limit: int = 100, name: str = "", status: str = "") -> List[DialogFlowResponse]:
        """列出对话流"""
        query = DialogFlow.all()
        if agent_id:
            query = query.filter(agent__id=agent_id)
        if name:
            query = query.filter(name__icontains=name)
        if status:
            query = query.filter(status=status)
        dialog_flows = await query.offset(skip).limit(limit).all()
        return [DialogFlowResponse.from_orm(df) for df in dialog_flows]
    
    @staticmethod
    async def update_dialog_flow(dialog_flow_id: int, data: DialogFlowUpdate) -> Optional[DialogFlowResponse]:
        """更新对话流"""
        dialog_flow = await DialogFlow.get_or_none(id=dialog_flow_id)
        if not dialog_flow:
            return None
        
        update_data = data.dict(exclude_unset=True)
        await dialog_flow.update_from_dict(update_data)
        await dialog_flow.save()
        
        return DialogFlowResponse.from_orm(dialog_flow)
    
    @staticmethod
    async def delete_dialog_flow(dialog_flow_id: int) -> bool:
        """删除对话流"""
        dialog_flow = await DialogFlow.get_or_none(id=dialog_flow_id)
        if not dialog_flow:
            return False
        
        await DialogFlowNode.filter(dialog_flow_id=dialog_flow_id).delete()
        await DialogFlowEdge.filter(dialog_flow_id=dialog_flow_id).delete()
        
        await dialog_flow.delete()
        return True
    
    @staticmethod
    async def create_node(data: DialogFlowNodeCreate) -> DialogFlowNodeResponse:
        """创建对话流节点"""
        node = await DialogFlowNode.create(**data.dict())
        return DialogFlowNodeResponse.from_orm(node)
    
    @staticmethod
    async def get_node(node_id: int) -> Optional[DialogFlowNodeResponse]:
        """获取对话流节点"""
        node = await DialogFlowNode.get_or_none(id=node_id)
        if not node:
            return None
        return DialogFlowNodeResponse.from_orm(node)
    
    @staticmethod
    async def list_nodes(dialog_flow_id: int) -> List[DialogFlowNodeResponse]:
        """列出对话流节点"""
        nodes = await DialogFlowNode.filter(dialog_flow_id=dialog_flow_id).all()
        return [DialogFlowNodeResponse.from_orm(node) for node in nodes]
    
    @staticmethod
    async def update_node(node_id: int, data: DialogFlowNodeUpdate) -> Optional[DialogFlowNodeResponse]:
        """更新对话流节点"""
        node = await DialogFlowNode.get_or_none(id=node_id)
        if not node:
            return None
        
        update_data = data.dict(exclude_unset=True)
        await node.update_from_dict(update_data)
        await node.save()
        
        return DialogFlowNodeResponse.from_orm(node)
    
    @staticmethod
    async def delete_node(node_id: int) -> bool:
        """删除对话流节点"""
        node = await DialogFlowNode.get_or_none(id=node_id)
        if not node:
            return False
        
        await DialogFlowEdge.filter(source_node_id=node_id).delete()
        await DialogFlowEdge.filter(target_node_id=node_id).delete()
        
        await node.delete()
        return True
    
    @staticmethod
    async def create_edge(data: DialogFlowEdgeCreate) -> DialogFlowEdgeResponse:
        """创建对话流边"""
        edge = await DialogFlowEdge.create(**data.dict())
        return DialogFlowEdgeResponse.from_orm(edge)
    
    @staticmethod
    async def get_edge(edge_id: int) -> Optional[DialogFlowEdgeResponse]:
        """获取对话流边"""
        edge = await DialogFlowEdge.get_or_none(id=edge_id)
        if not edge:
            return None
        return DialogFlowEdgeResponse.from_orm(edge)
    
    @staticmethod
    async def list_edges(dialog_flow_id: int) -> List[DialogFlowEdgeResponse]:
        """列出对话流边"""
        edges = await DialogFlowEdge.filter(dialog_flow_id=dialog_flow_id).all()
        return [DialogFlowEdgeResponse.from_orm(edge) for edge in edges]
    
    @staticmethod
    async def update_edge(edge_id: int, data: DialogFlowEdgeUpdate) -> Optional[DialogFlowEdgeResponse]:
        """更新对话流边"""
        edge = await DialogFlowEdge.get_or_none(id=edge_id)
        if not edge:
            return None
        
        update_data = data.dict(exclude_unset=True)
        await edge.update_from_dict(update_data)
        await edge.save()
        
        return DialogFlowEdgeResponse.from_orm(edge)
    
    @staticmethod
    async def delete_edge(edge_id: int) -> bool:
        """删除对话流边"""
        edge = await DialogFlowEdge.get_or_none(id=edge_id)
        if not edge:
            return False
        
        await edge.delete()
        return True

    @staticmethod
    def _parse_flow_data(dialog_flow: DialogFlow) -> Dict[str, Any]:
        """解析对话流结构数据"""
        flow_data = dialog_flow.flow_data or {}
        if isinstance(flow_data, str):
            try:
                flow_data = json.loads(flow_data)
            except json.JSONDecodeError:
                logger.error("对话流结构解析失败")
                return {"nodes": [], "edges": []}
        return flow_data

    @staticmethod
    def _build_node_map(nodes: List[Dict]) -> Dict[str, Dict]:
        """构建节点ID到节点的映射"""
        return {node.get("id"): node for node in nodes}

    @staticmethod
    def _build_edge_map(edges: List[Dict]) -> Dict[str, List[Dict]]:
        """构建源节点ID到边列表的映射"""
        edge_map = {}
        for edge in edges:
            source = edge.get("source")
            if source not in edge_map:
                edge_map[source] = []
            edge_map[source].append(edge)
        return edge_map

    @staticmethod
    def _find_start_node(nodes: List[Dict]) -> Optional[Dict]:
        """找到开始节点"""
        for node in nodes:
            if node.get("type") == "start":
                return node
        return None

    @staticmethod
    async def _execute_node(
        node: Dict,
        variables: Dict[str, Any],
        input_data: Dict[str, Any],
        sse_yield_func=None
    ) -> Dict[str, Any]:
        """执行单个节点"""
        node_type = node.get("type")
        node_data = node.get("data", {})
        result = {"type": node_type, "node_id": node.get("id"), "output": {}}

        if node_type == "start":
            result["output"] = {"message": "对话流开始"}
        
        elif node_type == "end":
            result["output"] = {"message": "对话流结束"}
        
        elif node_type == "input":
            input_key = node_data.get("input_var", "input")
            input_types = node_data.get("input_types", ["text"])
            output = {input_key: input_data.get("text", "")}
            
            if isinstance(input_types, str):
                input_types = [input_types]
            
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
            
            result["output"] = output
        
        elif node_type == "output":
            output_var = node_data.get("output_var", "output")
            result["output"] = {output_var: variables.get(output_var, "")}
        
        elif node_type == "message":
            content = node_data.get("content", "")
            content = DialogFlowService._replace_variables(content, variables)
            message_type = node_data.get("message_type", "text")
            buttons = node_data.get("buttons", [])
            result["output"] = {"message": content, "message_type": message_type, "buttons": buttons}
            if sse_yield_func:
                await sse_yield_func({
                    "type": "message",
                    "node_id": node.get("id"),
                    "content": content,
                    "message_type": message_type,
                    "buttons": buttons
                })
        
        elif node_type == "text":
            content = node_data.get("content", "")
            content = DialogFlowService._replace_variables(content, variables)
            output_var = node_data.get("output_var", "text")
            result["output"] = {output_var: content}
        
        elif node_type == "image":
            image_url = node_data.get("image_url", "")
            image_url = DialogFlowService._replace_variables(image_url, variables)
            image_alt = node_data.get("image_alt", "")
            image_alt = DialogFlowService._replace_variables(image_alt, variables)
            analyze_image = node_data.get("analyze_image", False)
            
            result["output"] = {"image_url": image_url, "image_alt": image_alt, "analyze_image": analyze_image}
            
            if sse_yield_func:
                await sse_yield_func({
                    "type": "image",
                    "node_id": node.get("id"),
                    "image_url": image_url,
                    "image_alt": image_alt
                })
            
            if analyze_image and image_url:
                result["output"]["image_analysis"] = await DialogFlowService._analyze_image_with_llm(
                    image_url, node, variables, input_data, sse_yield_func
                )
        
        elif node_type == "voice":
            text = node_data.get("text", "")
            text = DialogFlowService._replace_variables(text, variables)
            voice_type = node_data.get("voice_type", "tts")
            voice_provider_id = node_data.get("voice_provider_id")
            language = node_data.get("language", "zh")
            
            result["output"] = {"text": text, "voice_type": voice_type, "language": language}
            
            if voice_type == "tts":
                audio_url = await DialogFlowService._execute_voice_tts(
                    text, voice_provider_id, language, sse_yield_func
                )
                result["output"]["audio_url"] = audio_url
            elif voice_type == "asr":
                audio_url = node_data.get("audio_url", "")
                if audio_url:
                    audio_url = DialogFlowService._replace_variables(audio_url, variables)
                    recognized_text = await DialogFlowService._execute_voice_asr(
                        audio_url, voice_provider_id, language, sse_yield_func
                    )
                    result["output"]["recognized_text"] = recognized_text
                    result["output"]["audio_url"] = audio_url
            
            if sse_yield_func:
                await sse_yield_func({
                    "type": "voice",
                    "node_id": node.get("id"),
                    "text": text,
                    "voice_type": voice_type,
                    "audio_url": result["output"].get("audio_url"),
                    "recognized_text": result["output"].get("recognized_text")
                })
        
        elif node_type == "llm":
            llm_result = await DialogFlowService._execute_llm_node(
                node, variables, input_data, sse_yield_func
            )
            result["output"] = llm_result
        
        elif node_type == "knowledge_retrieval":
            kr_result = await DialogFlowService._execute_knowledge_retrieval_node(
                node, variables, sse_yield_func
            )
            result["output"] = kr_result
        
        elif node_type == "api":
            api_result = await DialogFlowService._execute_api_node(
                node, variables, sse_yield_func
            )
            result["output"] = api_result
        
        elif node_type == "condition":
            condition = node_data.get("condition", "")
            condition = DialogFlowService._replace_variables(condition, variables)
            try:
                result["output"] = {"result": eval(condition, {}, variables)}
            except Exception as e:
                logger.error(f"条件节点执行失败: {e}")
                result["output"] = {"result": False}
        
        elif node_type == "question":
            question = node_data.get("question", "")
            question = DialogFlowService._replace_variables(question, variables)
            result["output"] = {"question": question}
        
        else:
            logger.warning(f"未知节点类型: {node_type}")
            result["output"] = {"message": f"未处理的节点类型: {node_type}"}

        return result

    @staticmethod
    async def _execute_llm_node(
        node: Dict,
        variables: Dict[str, Any],
        input_data: Dict[str, Any],
        sse_yield_func=None
    ) -> Dict[str, Any]:
        """执行大模型节点"""
        node_data = node.get("data", {})
        model_id = node_data.get("llm_model_id")
        prompt = node_data.get("llm_prompt", "")
        temperature = node_data.get("llm_temperature", 0.7)
        max_tokens = node_data.get("llm_max_tokens", 1024)
        stream = node_data.get("llm_stream", True)
        output_var = node_data.get("output_var", "response")

        prompt = DialogFlowService._replace_variables(prompt, variables)

        image_urls = DialogFlowService._extract_image_urls(variables, input_data)

        if not model_id:
            return {output_var: "请先配置大模型"}

        try:
            from base.plugins.llm.models.model import LLMModel
            from base.plugins.llm.models.api_key import LLMApiKey
            from base.plugins.llm.services.chat_service import ChatService

            model = await LLMModel.get_or_none(id=model_id).prefetch_related('provider')
            if not model:
                return {output_var: "模型不存在"}

            if model.status != "active":
                return {output_var: "模型未启用"}

            api_key_obj = await LLMApiKey.filter(
                model_id=model.id
            ).first()
            if not api_key_obj:
                api_key_obj = await LLMApiKey.filter(
                    provider_id=model.provider_id,
                    model_id__isnull=True
                ).first()
            if not api_key_obj:
                return {output_var: "没有可用的API密钥"}

            endpoint_url = model.endpoint_url or api_key_obj.endpoint_url or model.provider.official_url
            if endpoint_url:
                endpoint_url = endpoint_url.rstrip('/')
                if endpoint_url.endswith('/chat/completions'):
                    endpoint_url = endpoint_url[:-len('/chat/completions')]
                if '/responses' in endpoint_url:
                    endpoint_url = endpoint_url.split('/responses')[0]

            credentials = api_key_obj.get_credentials()

            service = await ChatService.get_provider_service(
                provider_name_en=model.provider.name_en,
                api_key=credentials.get("api_key", ""),
                endpoint_url=endpoint_url,
                api_secret=credentials.get("api_secret", ""),
                call_mode=credentials.get("call_mode", "vendor_sdk"),
            )

            messages = []
            if input_data.get("history"):
                for msg in input_data["history"]:
                    msg_content = msg.get("content")
                    if isinstance(msg_content, list):
                        messages.append({"role": msg.get("role"), "content": msg_content})
                    else:
                        messages.append({"role": msg.get("role"), "content": msg_content})

            if image_urls and model.supports_vision:
                content = [{"type": "text", "text": prompt}]
                for img_url in image_urls:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": img_url}
                    })
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "user", "content": prompt})

            if stream and sse_yield_func:
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
                        await sse_yield_func({
                            "type": "stream",
                            "node_id": node.get("id"),
                            "content": content,
                            "full_content": full_response
                        })
                return {output_var: full_response}
            else:
                result = await service.chat(
                    model=model.model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=1.0,
                    stream=False
                )
                response_text = result["choices"][0]["message"]["content"]
                if sse_yield_func:
                    await sse_yield_func({
                        "type": "llm_complete",
                        "node_id": node.get("id"),
                        "content": response_text
                    })
                return {output_var: response_text}

        except Exception as e:
            logger.error(f"大模型节点执行失败: {e}", exc_info=True)
            return {output_var: f"大模型调用失败: {str(e)}"}

    @staticmethod
    async def _execute_knowledge_retrieval_node(
        node: Dict,
        variables: Dict[str, Any],
        sse_yield_func=None
    ) -> Dict[str, Any]:
        """执行知识检索节点"""
        node_data = node.get("data", {})
        query = node_data.get("query", "")
        top_k = node_data.get("top_k", 3)
        output_var = node_data.get("output_var", "knowledge")

        query = DialogFlowService._replace_variables(query, variables)

        if sse_yield_func:
            await sse_yield_func({
                "type": "knowledge_retrieval",
                "node_id": node.get("id"),
                "query": query
            })

        try:
            from base.plugins.agent.services.rag_service import RAGService
            results = await RAGService.search(query, top_k=top_k)
            contexts = [r.get("content", "") for r in results]
            result = {"results": results, "contexts": "\n".join(contexts)}
            
            if sse_yield_func:
                await sse_yield_func({
                    "type": "knowledge_result",
                    "node_id": node.get("id"),
                    "results": results
                })
            
            return {output_var: result}
        except Exception as e:
            logger.error(f"知识检索失败: {e}", exc_info=True)
            return {output_var: f"知识检索失败: {str(e)}"}

    @staticmethod
    async def _execute_api_node(
        node: Dict,
        variables: Dict[str, Any],
        sse_yield_func=None
    ) -> Dict[str, Any]:
        """执行API调用节点"""
        node_data = node.get("data", {})
        url = node_data.get("url", "")
        method = node_data.get("method", "GET")
        headers = node_data.get("headers", {})
        body = node_data.get("body", {})
        output_var = node_data.get("output_var", "api_result")

        url = DialogFlowService._replace_variables(url, variables)

        if isinstance(body, str):
            body = DialogFlowService._replace_variables(body, variables)
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass

        if sse_yield_func:
            await sse_yield_func({
                "type": "api_call",
                "node_id": node.get("id"),
                "url": url,
                "method": method
            })

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    data=body if isinstance(body, str) else None
                ) as response:
                    status = response.status
                    try:
                        result = await response.json()
                    except Exception:
                        result = await response.text()
                    
                    if sse_yield_func:
                        await sse_yield_func({
                            "type": "api_result",
                            "node_id": node.get("id"),
                            "status": status,
                            "result": result
                        })
                    
                    return {output_var: {"status": status, "result": result}}
        except Exception as e:
            logger.error(f"API调用失败: {e}", exc_info=True)
            return {output_var: f"API调用失败: {str(e)}"}

    @staticmethod
    def _replace_variables(text: str, variables: Dict[str, Any]) -> str:
        """替换文本中的变量"""
        if not text:
            return text
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            text = text.replace(placeholder, str(value))
        return text

    @staticmethod
    def _extract_image_urls(variables: Dict[str, Any], input_data: Dict[str, Any]) -> List[str]:
        """从变量和输入数据中提取图片URL列表"""
        image_urls = []
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg')
        
        for key, value in variables.items():
            if isinstance(value, str) and value:
                lower_val = value.lower()
                if key in ('image_url', 'image', 'img', 'picture', 'photo') or \
                   any(lower_val.endswith(ext) for ext in image_extensions) or \
                   ('http' in lower_val and any(ext in lower_val for ext in image_extensions)):
                    image_urls.append(value)
        
        if input_data:
            if isinstance(input_data.get('image_url'), str):
                image_urls.append(input_data['image_url'])
            elif isinstance(input_data.get('image_urls'), list):
                image_urls.extend([u for u in input_data['image_urls'] if isinstance(u, str)])
        
        seen = set()
        unique_urls = []
        for url in image_urls:
            if url and url not in seen:
                seen.add(url)
                unique_urls.append(url)
        return unique_urls

    @staticmethod
    async def _save_dialog_memory(
        agent_id: int,
        user_id: int,
        input_data: Dict[str, Any],
        variables: Dict[str, Any]
    ):
        """保存对话流执行结果到记忆"""
        try:
            from base.plugins.agent.services.memory_service import MemoryService
            from base.plugins.agent.schemas.memory import MemoryCreate

            memory_mode = "private"
            user_id_val = user_id

            input_text = input_data.get("text", "")
            if input_text:
                input_memory_data = MemoryCreate(
                    agent_id=agent_id,
                    content=f"用户输入: {input_text}",
                    type="short_term",
                    importance=0.8,
                    memory_mode=memory_mode,
                    user_id=user_id_val
                )
                await MemoryService.create_memory(input_memory_data)
                logger.info("对话流记忆保存: 输入内容已保存")

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

                    if content_str and len(content_str.strip()) > 0 and len(content_str) < 5000:
                        try:
                            importance = 0.9 if var_name in ["final_output", "response", "answer"] else 0.7
                            memory_data = MemoryCreate(
                                agent_id=agent_id,
                                content=f"{var_name}: {content_str}",
                                type="long_term",
                                importance=importance,
                                memory_mode=memory_mode,
                                user_id=user_id_val
                            )
                            await MemoryService.create_memory(memory_data)
                            saved_vars.add(var_name)
                            logger.info(f"对话流记忆保存: {var_name} 已保存")
                        except Exception as e:
                            logger.warning(f"保存记忆失败 {var_name}: {e}")

        except Exception as e:
            logger.warning(f"保存对话流记忆时出错: {e}")

    @staticmethod
    async def _analyze_image_with_llm(
        image_url: str,
        node: Dict[str, Any],
        variables: Dict[str, Any],
        input_data: Dict[str, Any],
        sse_yield_func=None
    ) -> Dict[str, Any]:
        """使用大模型分析图片"""
        try:
            from base.plugins.llm.models.model import LLMModel
            from base.plugins.llm.models.api_key import LLMApiKey
            from base.plugins.llm.services.chat_service import ChatService
            
            node_data = node.get("data", {})
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
            analysis_prompt = DialogFlowService._replace_variables(analysis_prompt, variables)
            
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
            
            if sse_yield_func:
                await sse_yield_func({
                    "type": "image_analysis",
                    "node_id": node.get("id"),
                    "image_url": image_url,
                    "analysis": response_text
                })
            
            return {"analysis": response_text}
            
        except Exception as e:
            logger.error(f"图片分析失败: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _execute_voice_tts(
        text: str,
        voice_provider_id: int = None,
        language: str = "zh",
        sse_yield_func=None
    ) -> str:
        """执行TTS语音合成"""
        try:
            from base.plugins.llm.services.voice_helper import VoiceServiceHelper
            
            if not text:
                return ""
            
            if not voice_provider_id:
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
            
            if sse_yield_func:
                await sse_yield_func({
                    "type": "voice_tts",
                    "text": text,
                    "audio_url": audio_url
                })
            
            return audio_url
            
        except Exception as e:
            logger.error(f"TTS失败: {e}")
            return ""

    @staticmethod
    async def _execute_voice_asr(
        audio_url: str,
        voice_provider_id: int = None,
        language: str = "zh",
        sse_yield_func=None
    ) -> str:
        """执行ASR语音识别"""
        try:
            from base.plugins.llm.services.voice_helper import VoiceServiceHelper
            
            if not audio_url:
                return ""
            
            if not voice_provider_id:
                return ""
            
            service = await VoiceServiceHelper.get_voice_service(voice_provider_id)
            
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url)
                audio_data = response.content
            
            result = await service.file_asr(
                audio_file=audio_url,
                format="mp3",
                language=language
            )
            
            recognized_text = result.get("text", "")
            
            if sse_yield_func:
                await sse_yield_func({
                    "type": "voice_asr",
                    "audio_url": audio_url,
                    "recognized_text": recognized_text
                })
            
            return recognized_text
            
        except Exception as e:
            logger.error(f"ASR失败: {e}")
            return ""

    @staticmethod
    def _evaluate_condition(edge: Dict, variables: Dict[str, Any]) -> bool:
        """评估边的条件"""
        condition = edge.get("condition", "")
        if not condition:
            return True
        condition = DialogFlowService._replace_variables(condition, variables)
        try:
            return bool(eval(condition, {}, variables))
        except Exception:
            return False

    @staticmethod
    def should_use_sse(dialog_flow: DialogFlow) -> bool:
        """判断是否应该使用SSE模式"""
        flow_data = DialogFlowService._parse_flow_data(dialog_flow)
        nodes = flow_data.get("nodes", [])
        
        for node in nodes:
            node_data = node.get("data", {})
            if node.get("type") == "llm":
                stream_val = node_data.get("llm_stream", True)
                is_streaming = stream_val is True or (isinstance(stream_val, str) and stream_val.lower() == 'true')
                if is_streaming:
                    return True
        
        for node in nodes:
            if node.get("type") in ("knowledge_retrieval", "api"):
                return True
        
        has_condition = any(n.get("type") == "condition" for n in nodes)
        if has_condition:
            return True
        
        return False

    @staticmethod
    async def execute_dialog_flow(*args, **kwargs) -> DialogFlowExecutionResponse:
        """执行对话流（非流式）"""
        if len(args) == 1 and hasattr(args[0], 'dialog_flow_id'):
            data = args[0]
            dialog_flow_id = data.dialog_flow_id
            input_data = data.input_data
            agent_id = data.agent_id
            user_id = data.user_id
        else:
            dialog_flow_id = kwargs.get('dialog_flow_id') or (args[0] if args else None)
            input_data = kwargs.get('input_data') or (args[1] if len(args) > 1 else None)
            agent_id = kwargs.get('agent_id') or (args[2] if len(args) > 2 else None)
            user_id = kwargs.get('user_id') or (args[3] if len(args) > 3 else None)
        
        execution_data = {
            "dialog_flow_id": dialog_flow_id,
            "agent_id": agent_id,
            "user_id": user_id,
            "input_data": input_data or {}
        }
        execution = await DialogFlowExecution.create(**execution_data)
        
        try:
            dialog_flow = await DialogFlow.get_or_none(id=dialog_flow_id)
            if not dialog_flow:
                raise ValueError("对话流不存在")
            
            flow_data = DialogFlowService._parse_flow_data(dialog_flow)
            nodes = flow_data.get("nodes", [])
            edges = flow_data.get("edges", [])
            
            node_map = DialogFlowService._build_node_map(nodes)
            edge_map = DialogFlowService._build_edge_map(edges)
            
            start_node = DialogFlowService._find_start_node(nodes)
            if not start_node:
                raise ValueError("未找到开始节点")
            
            variables = {}
            variables.update(input_data or {})
            
            if agent_id and user_id:
                try:
                    from base.plugins.agent.services.memory_service import MemoryService
                    user_memories = await MemoryService.get_memories_by_agent(
                        agent_id=agent_id,
                        user_id=user_id
                    )
                    if user_memories:
                        memory_text = "\n".join([f"- {m.content}" for m in user_memories])
                        variables["memory"] = memory_text
                        variables["user_id"] = user_id
                except Exception as e:
                    logger.warning(f"检索用户记忆失败: {e}")
            
            execution_path = []
            
            current_node_id = start_node.get("id")
            
            while current_node_id:
                current_node = node_map.get(current_node_id)
                if not current_node:
                    break
                
                node_result = await DialogFlowService._execute_node(
                    current_node, variables, input_data or {}
                )
                
                execution_path.append({
                    "node_id": current_node_id,
                    "node_type": current_node.get("type"),
                    "output": node_result.get("output", {})
                })
                
                variables.update(node_result.get("output", {}))
                
                if current_node.get("type") == "end":
                    break
                
                next_edges = edge_map.get(current_node_id, [])
                current_node_id = None
                
                for edge in next_edges:
                    if DialogFlowService._evaluate_condition(edge, variables):
                        current_node_id = edge.get("target")
                        break
            
            execution.status = "completed"
            execution.execution_path = execution_path
            execution.output_data = variables
            execution.completed_at = datetime.utcnow()
            await execution.save()
            
            if agent_id and user_id:
                await DialogFlowService._save_dialog_memory(
                    agent_id=agent_id,
                    user_id=user_id,
                    input_data=input_data or {},
                    variables=variables
                )
            
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            await execution.save()
        
        return DialogFlowExecutionResponse.from_orm(execution)

    @staticmethod
    async def sse_execution_generator(
        dialog_flow: DialogFlow,
        input_data: Dict[str, Any],
        execution_id: str = None
    ) -> AsyncGenerator[str, None]:
        """SSE事件生成器 - 实时推送执行过程"""
        import asyncio
        
        def send_event(event_data):
            return f"data: {json.dumps({**event_data, 'timestamp': datetime.now().isoformat()}, ensure_ascii=False)}\n\n"
        
        event_queue = asyncio.Queue()
        
        async def push_event(event_data):
            await event_queue.put(send_event(event_data))
        
        await push_event({'type': 'start', 'execution_id': execution_id, 'message': '开始执行对话流'})
        
        async def execute_flow():
            try:
                flow_data = DialogFlowService._parse_flow_data(dialog_flow)
                nodes = flow_data.get("nodes", [])
                edges = flow_data.get("edges", [])
                
                node_map = DialogFlowService._build_node_map(nodes)
                edge_map = DialogFlowService._build_edge_map(edges)
                
                start_node = DialogFlowService._find_start_node(nodes)
                if not start_node:
                    await push_event({'type': 'error', 'message': '未找到开始节点'})
                    return
                
                variables = {}
                variables.update(input_data or {})
                
                agent_id = input_data.get('agent_id') if input_data else None
                user_id = input_data.get('user_id') if input_data else None
                
                if agent_id and user_id:
                    try:
                        from base.plugins.agent.services.memory_service import MemoryService
                        user_memories = await MemoryService.get_memories_by_agent(
                            agent_id=agent_id,
                            user_id=user_id
                        )
                        if user_memories:
                            memory_text = "\n".join([f"- {m.content}" for m in user_memories])
                            variables["memory"] = memory_text
                            variables["user_id"] = user_id
                    except Exception as e:
                        logger.warning(f"检索用户记忆失败: {e}")
                
                execution_path = []
                
                current_node_id = start_node.get("id")
                
                while current_node_id:
                    current_node = node_map.get(current_node_id)
                    if not current_node:
                        break
                    
                    await push_event({'type': 'node_start', 'node_id': current_node_id, 'node_type': current_node.get("type")})
                    
                    node_result = await DialogFlowService._execute_node(
                        current_node, variables, input_data or {},
                        sse_yield_func=push_event
                    )
                    
                    execution_path.append({
                        "node_id": current_node_id,
                        "node_type": current_node.get("type"),
                        "output": node_result.get("output", {})
                    })
                    
                    variables.update(node_result.get("output", {}))
                    
                    await push_event({'type': 'node_complete', 'node_id': current_node_id, 'output': node_result.get("output", {})})
                    
                    if current_node.get("type") == "end":
                        break
                    
                    next_edges = edge_map.get(current_node_id, [])
                    current_node_id = None
                    
                    for edge in next_edges:
                        if DialogFlowService._evaluate_condition(edge, variables):
                            current_node_id = edge.get("target")
                            break
                
                agent_id = input_data.get('agent_id') if input_data else None
                user_id = input_data.get('user_id') if input_data else None
                if agent_id and user_id:
                    await DialogFlowService._save_dialog_memory(
                        agent_id=agent_id,
                        user_id=user_id,
                        input_data=input_data or {},
                        variables=variables
                    )
                
                await push_event({
                    'type': 'complete',
                    'execution_id': execution_id,
                    'variables': variables,
                    'execution_path': execution_path
                })
                
            except Exception as e:
                logger.error(f"对话流执行失败: {e}", exc_info=True)
                await push_event({'type': 'error', 'message': str(e)})
        
        task = asyncio.create_task(execute_flow())
        
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=300)
                yield event
            except asyncio.TimeoutError:
                logger.warning("SSE事件队列超时")
                break
            
            if task.done() and event_queue.empty():
                break
        
        if not task.done():
            task.cancel()

    @staticmethod
    async def get_execution(execution_id: int) -> Optional[DialogFlowExecutionResponse]:
        """获取对话流执行记录"""
        execution = await DialogFlowExecution.get_or_none(id=execution_id)
        if not execution:
            return None
        return DialogFlowExecutionResponse.from_orm(execution)
    
    @staticmethod
    async def list_executions(dialog_flow_id: Optional[int] = None, agent_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[DialogFlowExecutionResponse]:
        """列出对话流执行记录"""
        query = DialogFlowExecution.all()
        if dialog_flow_id:
            query = query.filter(dialog_flow_id=dialog_flow_id)
        if agent_id:
            query = query.filter(agent_id=agent_id)
        
        executions = await query.order_by("-started_at").offset(skip).limit(limit).all()
        return [DialogFlowExecutionResponse.from_orm(execution) for execution in executions]

    @staticmethod
    async def execute_dialog_flow_with_langgraph(
        dialog_flow_id: int,
        input_data: Dict[str, Any],
        session_id: str = None,
        user_id: int = None,
        checkpoint_id: str = None,
        sse_yield_func=None
    ) -> Dict[str, Any]:
        """
        使用LangGraph执行对话流，支持多轮对话和Checkpoint
        
        Args:
            dialog_flow_id: 对话流ID
            input_data: 输入数据
            session_id: 会话ID（用于多轮对话）
            user_id: 用户ID（用于记忆管理）
            checkpoint_id: 检查点ID（用于恢复指定检查点）
            sse_yield_func: SSE推送回调函数
            
        Returns:
            执行结果
        """
        from base.plugins.agent.services.dialog_flow_langgraph import DialogFlowLangGraphExecutor
        import uuid
        
        dialog_flow = await DialogFlow.get_or_none(id=dialog_flow_id)
        if not dialog_flow:
            return {"success": False, "message": "对话流不存在"}
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        actor = {"id": user_id or "anonymous", "type": "user"}
        
        result = await DialogFlowLangGraphExecutor.execute_dialog_flow(
            dialog_flow=dialog_flow,
            input_data=input_data,
            actor=actor,
            sse_yield_func=sse_yield_func,
            session_id=session_id,
            user_id=user_id,
            checkpoint_id=checkpoint_id
        )
        
        # 保存执行记录
        try:
            execution_data = {
                "dialog_flow_id": dialog_flow_id,
                "user_id": user_id,
                "input_data": input_data,
                "output_data": result.get("output", {}),
                "status": "completed" if result.get("success") else "failed",
                "execution_path": result.get("execution_trace", [])
            }
            if not result.get("success"):
                execution_data["error_message"] = result.get("message", "")
            
            await DialogFlowExecution.create(**execution_data)
        except Exception as e:
            logger.warning(f"保存执行记录失败: {e}")
        
        result["session_id"] = session_id
        return result

    @staticmethod
    async def get_user_checkpoints(
        dialog_flow_id: int,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        获取用户的所有检查点
        
        Args:
            dialog_flow_id: 对话流ID
            user_id: 用户ID
            
        Returns:
            检查点列表
        """
        from base.plugins.agent.services.checkpoint_service import CheckpointService
        
        checkpoint_service = CheckpointService.get_instance()
        actor = {"id": user_id, "type": "user"}
        all_checkpoints = checkpoint_service.get_user_checkpoints(actor)
        
        dialog_flow_checkpoints = [
            cp for cp in all_checkpoints
            if cp.get("metadata", {}).get("dialog_flow_id") == dialog_flow_id
        ]
        
        return dialog_flow_checkpoints

    @staticmethod
    async def get_session_checkpoints(
        session_id: str,
        user_id: int
    ) -> List[Dict[str, Any]]:
        """
        获取会话的所有检查点
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
            
        Returns:
            检查点列表
        """
        from base.plugins.agent.services.checkpoint_service import CheckpointService
        
        checkpoint_service = CheckpointService.get_instance()
        actor = {"id": user_id, "type": "user"}
        return checkpoint_service.get_session_checkpoints(actor, session_id)

    @staticmethod
    async def get_checkpoint_detail(
        checkpoint_id: str,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        获取检查点详情
        
        Args:
            checkpoint_id: 检查点ID
            user_id: 用户ID
            
        Returns:
            检查点详情
        """
        from base.plugins.agent.services.checkpoint_service import CheckpointService
        
        checkpoint_service = CheckpointService.get_instance()
        actor = {"id": user_id, "type": "user"}
        return checkpoint_service.get_checkpoint(actor, checkpoint_id)