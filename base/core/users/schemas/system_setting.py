"""
系统设置相关的Pydantic模型
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class SystemSettingBase(BaseModel):
    """系统设置基础模型"""
    key: str = Field(..., max_length=100, description="设置键")
    value: Optional[str] = Field(None, description="设置值")
    name: str = Field(..., max_length=100, description="设置名称")
    description: Optional[str] = Field(None, max_length=500, description="设置描述")
    setting_type: str = Field(default="string", max_length=50, description="设置类型")
    is_active: bool = Field(default=True, description="是否激活")
    sort: int = Field(default=0, description="排序")


class SystemSettingCreate(SystemSettingBase):
    """创建系统设置模型"""
    pass


class SystemSettingUpdate(BaseModel):
    """更新系统设置模型"""
    value: Optional[str] = Field(None, description="设置值")
    name: Optional[str] = Field(None, max_length=100, description="设置名称")
    description: Optional[str] = Field(None, max_length=500, description="设置描述")
    setting_type: Optional[str] = Field(None, max_length=50, description="设置类型")
    is_active: Optional[bool] = Field(None, description="是否激活")
    sort: Optional[int] = Field(None, description="排序")


class SystemSettingResponse(BaseModel):
    """系统设置响应模型"""
    id: int
    key: str
    value: Optional[str] = None
    name: str
    description: Optional[str] = None
    setting_type: str
    is_active: bool
    sort: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemSettingListResponse(BaseModel):
    """系统设置列表响应模型"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: list[SystemSettingResponse] = Field(..., description="系统设置列表")
