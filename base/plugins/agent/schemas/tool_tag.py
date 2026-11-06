"""
Tool Tag schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ToolTagBase(BaseModel):
    """Base tool tag schema"""
    name: str = Field(..., description="标签名称")
    description: Optional[str] = Field(None, description="标签描述")
    color: Optional[str] = Field("#409eff", description="标签颜色")
    sort_order: Optional[int] = Field(0, description="排序")
    enabled: Optional[bool] = Field(True, description="是否启用")


class ToolTagCreate(ToolTagBase):
    """Create tool tag schema"""
    pass


class ToolTagUpdate(BaseModel):
    """Update tool tag schema"""
    name: Optional[str] = Field(None, description="标签名称")
    description: Optional[str] = Field(None, description="标签描述")
    color: Optional[str] = Field(None, description="标签颜色")
    sort_order: Optional[int] = Field(None, description="排序")
    enabled: Optional[bool] = Field(None, description="是否启用")


class ToolTagResponse(BaseModel):
    """Tool tag response schema"""
    id: int = Field(..., description="标签ID")
    name: str = Field(..., description="标签名称")
    description: Optional[str] = Field(None, description="标签描述")
    color: str = Field(..., description="标签颜色")
    sort_order: int = Field(..., description="排序")
    enabled: bool = Field(..., description="是否启用")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        from_attributes = True


class ToolTagWithCountResponse(ToolTagResponse):
    """Tool tag response with tool count"""
    tool_count: int = Field(0, description="关联工具数量")
    
    class Config:
        from_attributes = True
