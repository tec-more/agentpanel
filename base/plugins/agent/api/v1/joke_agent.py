"""
笑话智能体调试接口
整合检索增强、大模型调用和技能调用
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from base.common.response import success_response, fail_response

joke_agent_router = APIRouter(prefix="/joke-agent", tags=["笑话智能体"])


class JokeAgentRequest(BaseModel):
    """笑话智能体请求"""
    text: str
    agent_id: Optional[int] = None
    enable_rag: bool = True
    enable_voice: bool = False
    model_name: str = "gpt-3.5-turbo"


class JokeAgentResponse(BaseModel):
    """笑话智能体响应"""
    success: bool
    result: Optional[str] = None
    rag_context: Optional[Dict[str, Any]] = None
    skill_result: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


@joke_agent_router.post("/chat", response_model=JokeAgentResponse)
async def joke_agent_chat(request: JokeAgentRequest):
    """
    笑话智能体对话（文本输入）
    
    流程：
    1. 检索增强（RAG）- 从知识库和记忆中检索相关内容
    2. 大模型处理 - 使用检索到的上下文生成回复
    3. 调用技能 - 根据需要调用笑话相关技能
    
    Args:
        request: 笑话智能体请求
        
    Returns:
        处理结果
    """
    try:
        from base.plugins.completion.services.completion_service import CompletionService
        from base.plugins.agent.services.memory_service import MemoryService
        from base.plugins.agent.services.skill_service import SkillService
        from base.plugins.agent.models.agent import Agent
        
        result = {
            "success": True,
            "result": "",
            "rag_context": {},
            "skill_result": None
        }
        
        input_text = request.text
        agent_id = request.agent_id
        
        # 步骤1：检索增强（RAG）
        if request.enable_rag and agent_id:
            # 检索相关记忆
            relevant_memories = await MemoryService.retrieve_relevant_memories(
                agent_id, 
                input_text, 
                k=5
            )
            
            # 构建RAG上下文
            rag_context = {
                "relevant_memories": [memory.content for memory in relevant_memories],
                "memory_count": len(relevant_memories)
            }
            
            # 如果有相关记忆，构建增强的输入
            if relevant_memories:
                context_text = "相关记忆：\n"
                for memory in relevant_memories:
                    context_text += f"- {memory.content}\n"
                context_text += f"\n用户输入：{input_text}"
                enhanced_input = context_text
            else:
                enhanced_input = input_text
            
            result["rag_context"] = rag_context
        else:
            enhanced_input = input_text
        
        # 步骤2：大模型处理
        system_prompt = """你是一个幽默风趣的笑话助手，擅长讲笑话、翻译笑话和创作笑话。

你的特点：
1. 幽默风趣，善于用轻松的语气回复
2. 知识丰富，了解各种类型的笑话
3. 善于理解用户意图，提供合适的笑话内容
4. 可以根据上下文创作新的笑话

回复要求：
1. 保持幽默风趣的语气
2. 如果用户要求讲笑话，提供有趣的笑话
3. 如果用户要求翻译笑话，准确翻译并保持幽默感
4. 如果用户要求创作笑话，根据主题创作原创笑话
5. 回复要简洁明了，不要太长
"""
        
        try:
            llm_result = await CompletionService.chat_completion(
                model=request.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": enhanced_input}
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            if llm_result.get("success"):
                result["result"] = llm_result.get("content", "")
            else:
                result["result"] = "抱歉，我暂时无法生成回复。"
        except Exception as e:
            result["result"] = f"大模型调用失败：{str(e)}"
        
        # 步骤3：调用技能（如果需要）
        if agent_id:
            try:
                agent = await Agent.get_or_none(id=agent_id)
                if agent:
                    skills = await agent.skills.all()
                    if skills:
                        # 调用第一个技能
                        skill = skills[0]
                        skill_result = await SkillService.execute_skill(
                            skill.id, 
                            {
                                "input_text": input_text,
                                "model_name": request.model_name,
                                "relevant_memories": result["rag_context"].get("relevant_memories", [])
                            }
                        )
                        result["skill_result"] = skill_result
            except Exception as e:
                result["skill_result"] = {"error": str(e)}
        
        return JokeAgentResponse(**result)
        
    except Exception as e:
        return JokeAgentResponse(
            success=False,
            message=f"处理失败: {str(e)}"
        )


@joke_agent_router.post("/chat/voice")
async def joke_agent_chat_voice(
    audio: UploadFile = File(..., description="音频文件"),
    agent_id: Optional[int] = Form(None, description="智能体ID"),
    enable_rag: bool = Form(True, description="是否启用RAG"),
    model_name: str = Form("gpt-3.5-turbo", description="大模型名称")
):
    """
    笑话智能体对话（语音输入）
    
    流程：
    1. 语音识别（ASR）- 将语音转换为文本
    2. 检索增强（RAG）- 从知识库和记忆中检索相关内容
    3. 大模型处理 - 使用检索到的上下文生成回复
    4. 语音合成（TTS）- 将回复转换为语音（可选）
    
    Args:
        audio: 音频文件
        agent_id: 智能体ID
        enable_rag: 是否启用RAG
        model_name: 大模型名称
        
    Returns:
        处理结果
    """
    try:
        from base.plugins.llm.services.asr_service import ASRService
        from base.plugins.llm.services.tts_service import TTSService
        import tempfile
        import os
        
        # 步骤1：语音识别
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(await audio.read())
            temp_file_path = temp_file.name
        
        try:
            asr_result = await ASRService.recognize_audio(
                audio_file=temp_file_path,
                model="paraformer-realtime-v2"
            )
            
            if not asr_result.get("success"):
                return fail_response(msg=f"语音识别失败: {asr_result.get('message')}")
            
            input_text = asr_result.get("text", "")
            
            # 步骤2-3：调用文本处理
            text_result = await joke_agent_chat(JokeAgentRequest(
                text=input_text,
                agent_id=agent_id,
                enable_rag=enable_rag,
                enable_voice=True,
                model_name=model_name
            ))
            
            # 步骤4：语音合成
            if text_result.success and text_result.result:
                tts_result = await TTSService.text_to_speech(
                    text=text_result.result,
                    voice="zh-femx-lingke",
                    output_format="mp3"
                )
                
                if tts_result.get("success"):
                    return success_response(
                        data={
                            "input_text": input_text,
                            "output_text": text_result.result,
                            "audio_url": tts_result.get("audio_url"),
                            "rag_context": text_result.rag_context,
                            "skill_result": text_result.skill_result
                        },
                        msg="处理成功"
                    )
                else:
                    return success_response(
                        data={
                            "input_text": input_text,
                            "output_text": text_result.result,
                            "rag_context": text_result.rag_context,
                            "skill_result": text_result.skill_result,
                            "tts_error": tts_result.get("message")
                        },
                        msg="语音合成失败，但文本处理成功"
                    )
            else:
                return fail_response(msg=text_result.message or "处理失败")
                
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except Exception as e:
        return fail_response(msg=f"处理失败: {str(e)}")


@joke_agent_router.get("/debug/{agent_id}")
async def debug_joke_agent(agent_id: int):
    """
    调试笑话智能体配置
    
    Args:
        agent_id: 智能体ID
        
    Returns:
        智能体配置信息
    """
    try:
        from base.plugins.agent.models.agent import Agent
        from base.plugins.agent.services.memory_service import MemoryService
        
        agent = await Agent.get_or_none(id=agent_id)
        if not agent:
            return fail_response(msg="智能体不存在", code=404)
        
        # 获取技能
        skills = await agent.skills.all()
        skill_list = []
        for skill in skills:
            skill_list.append({
                "id": skill.id,
                "name": skill.name,
                "type": skill.type,
                "description": skill.description,
                "status": skill.status
            })
        
        # 获取记忆统计
        memory_stats = await MemoryService.get_memory_stats(agent_id)
        
        # 获取大模型信息
        llm_info = None
        if agent.llm_model:
            llm_info = {
                "id": agent.llm_model.id,
                "model_id": agent.llm_model.model_id,
                "model_name": agent.llm_model.model_name,
                "provider": agent.llm_model.provider.name
            }
        
        return success_response(
            data={
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "description": agent.description,
                    "status": agent.status,
                    "system_prompt": agent.system_prompt,
                    "memory_capacity": agent.memory_capacity
                },
                "skills": skill_list,
                "memory_stats": memory_stats,
                "llm_model": llm_info
            },
            msg="获取调试信息成功"
        )
        
    except Exception as e:
        return fail_response(msg=f"获取调试信息失败: {str(e)}")
