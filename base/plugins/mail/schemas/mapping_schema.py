"""
事件→消息映射 Schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class MappingCreate(BaseModel):
    model: str = Field(..., max_length=100, description="业务表名")
    action: str = Field(..., max_length=20, description="create/update/delete")
    subtype_id: int = Field(..., description="关联子类型ID")
    condition_field: Optional[str] = Field(None, max_length=100)
    condition_value: Optional[str] = Field(None, max_length=255)
    name_template: Optional[str] = Field(None, max_length=500)
    body_template: Optional[str] = None
    is_active: bool = True
    notify_followers: bool = True
    notify_creator: bool = False


class MappingUpdate(BaseModel):
    subtype_id: Optional[int] = None
    condition_field: Optional[str] = Field(None, max_length=100)
    condition_value: Optional[str] = Field(None, max_length=255)
    name_template: Optional[str] = Field(None, max_length=500)
    body_template: Optional[str] = None
    is_active: Optional[bool] = None
    notify_followers: Optional[bool] = None
    notify_creator: Optional[bool] = None


class MappingListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
    model: Optional[str] = None
    action: Optional[str] = None
    is_active: Optional[bool] = None
