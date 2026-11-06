"""
消息子类型 Schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class SubtypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    model: Optional[str] = Field(None, max_length=100)
    default: bool = False
    internal: bool = False
    sequence: int = Field(default=10, ge=0)
    is_active: bool = True


class SubtypeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    model: Optional[str] = Field(None, max_length=100)
    default: Optional[bool] = None
    internal: Optional[bool] = None
    sequence: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class SubtypeListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
    model: Optional[str] = None
    is_active: Optional[bool] = None
    keyword: Optional[str] = Field(None, description="按 name/code 模糊搜索")
