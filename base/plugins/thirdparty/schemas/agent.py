"""
第三方平台智能体Pydantic模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class AgentBase(BaseModel):
    """智能体基础模型"""
    name: str = Field(..., description="智能体名称")
    platform_id: int = Field(..., description="所属平台ID")
    agent_id: str = Field(..., description="智能体ID")
    access_url: str = Field(..., description="智能体访问地址")
    status: str = Field(default="active", description="状态: active/inactive")
    description: Optional[str] = Field(None, description="描述")
    config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class AgentCreate(AgentBase):
    """创建智能体模型"""
    pass


class AgentUpdate(BaseModel):
    """更新智能体模型"""
    name: Optional[str] = Field(None, description="智能体名称")
    platform_id: Optional[int] = Field(None, description="所属平台ID")
    agent_id: Optional[str] = Field(None, description="智能体ID")
    access_url: Optional[str] = Field(None, description="智能体访问地址")
    status: Optional[str] = Field(None, description="状态: active/inactive")
    description: Optional[str] = Field(None, description="描述")
    config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class AgentResponse(AgentBase):
    """智能体响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True