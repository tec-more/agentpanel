"""
第三方平台Pydantic模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class PlatformBase(BaseModel):
    name: str = Field(..., description="平台名称")
    platform_type: str = Field(..., description="平台类型: saas/local")
    api_key: str = Field(..., description="API密钥")
    base_url: str = Field(..., description="平台基础URL")
    status: str = Field(default="active", description="状态: active/inactive")
    description: Optional[str] = Field(None, description="描述")
    config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class PlatformCreate(PlatformBase):
    """创建平台模型"""
    pass


class PlatformUpdate(BaseModel):
    """更新平台模型"""
    name: Optional[str] = Field(None, description="平台名称")
    platform_type: Optional[str] = Field(None, description="平台类型: dify/coze/other")
    api_key: Optional[str] = Field(None, description="API密钥")
    base_url: Optional[str] = Field(None, description="平台基础URL")
    status: Optional[str] = Field(None, description="状态: active/inactive")
    description: Optional[str] = Field(None, description="描述")
    config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class PlatformResponse(PlatformBase):
    """平台响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True