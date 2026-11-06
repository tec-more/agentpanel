"""
笑话翻译API路由
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from base.common.response import success_response, fail_response

joke_router = APIRouter(prefix="/joke", tags=["joke"])

class JokeTranslateRequest(BaseModel):
    """笑话翻译请求"""
    text: str
    source_lang: str = "auto"
    target_lang: str = "en"
    model_name: str = "gpt-3.5-turbo"

class JokeTranslateResponse(BaseModel):
    """笑话翻译响应"""
    success: bool
    translation: Optional[str] = None
    source_lang: Optional[str] = None
    target_lang: Optional[str] = None
    message: Optional[str] = None

@joke_router.post("/translate", response_model=JokeTranslateResponse)
async def translate_joke(request: JokeTranslateRequest):
    """
    翻译笑话（文本输入）
    
    Args:
        request: 笑话翻译请求
        
    Returns:
        翻译结果
    """
    try:
        from base.plugins.agent.skills.joke_translator import JokeTranslatorSkill
        
        result = JokeTranslatorSkill.execute({
            "input_text": request.text,
            "model_name": request.model_name,
            "source_lang": request.source_lang,
            "target_lang": request.target_lang
        })
        
        return JokeTranslateResponse(**result)
    except Exception as e:
        return JokeTranslateResponse(
            success=False,
            message=f"翻译失败: {str(e)}"
        )

@joke_router.post("/translate/voice")
async def translate_joke_voice(
    audio: UploadFile = File(..., description="音频文件"),
    source_lang: str = Form("auto", description="源语言"),
    target_lang: str = Form("en", description="目标语言"),
    model_name: str = Form("gpt-3.5-turbo", description="大模型名称")
):
    """
    翻译笑话（语音输入）
    
    Args:
        audio: 音频文件
        source_lang: 源语言
        target_lang: 目标语言
        model_name: 大模型名称
        
    Returns:
        翻译结果
    """
    try:
        # TODO: 实现语音识别功能
        # 1. 保存上传的音频文件
        # 2. 调用语音识别服务转换为文本
        # 3. 调用笑话翻译技能
        # 4. 可选：调用语音合成服务生成音频输出
        
        return JSONResponse(
            status_code=501,
            content={
                "success": False,
                "message": "语音输入功能尚未实现"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"翻译失败: {str(e)}"
            }
        )

@joke_router.get("/languages")
async def get_supported_languages():
    """
    获取支持的语言列表
    
    Returns:
        支持的语言列表
    """
    languages = [
        {"code": "auto", "name": "自动检测"},
        {"code": "zh", "name": "中文"},
        {"code": "en", "name": "英文"},
        {"code": "ja", "name": "日文"},
        {"code": "ko", "name": "韩文"},
        {"code": "fr", "name": "法文"},
        {"code": "de", "name": "德文"},
        {"code": "es", "name": "西班牙文"},
        {"code": "ru", "name": "俄文"},
        {"code": "pt", "name": "葡萄牙文"},
        {"code": "it", "name": "意大利文"}
    ]
    return success_response(data=languages, msg="获取支持的语言列表成功")

@joke_router.get("/examples")
async def get_joke_examples():
    """
    获取笑话示例
    
    Returns:
        笑话示例列表
    """
    examples = [
        {
            "id": 1,
            "text": "为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 = Dec 25",
            "source_lang": "zh",
            "target_lang": "en",
            "category": "程序员笑话"
        },
        {
            "id": 2,
            "text": "Why do programmers prefer dark mode? Because light attracts bugs!",
            "source_lang": "en",
            "target_lang": "zh",
            "category": "程序员笑话"
        },
        {
            "id": 3,
            "text": "小明：妈妈，我是不是领养的？妈妈：如果你是领养的，我早就把你退了！",
            "source_lang": "zh",
            "target_lang": "en",
            "category": "家庭笑话"
        },
        {
            "id": 4,
            "text": "I told my wife she was drawing her eyebrows too high. She looked surprised.",
            "source_lang": "en",
            "target_lang": "zh",
            "category": "双关语笑话"
        }
    ]
    return success_response(data=examples, msg="获取笑话示例成功")
