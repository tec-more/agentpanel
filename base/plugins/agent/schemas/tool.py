"""
Tool schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class ToolBase(BaseModel):
    """Base tool schema"""
    name: str = Field(..., description="Tool identifier")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Tool description")
    func_path: Optional[str] = Field(None, description="Function path")
    parameters: Optional[List[dict]] = Field(None, description="Parameter configuration")
    enabled: bool = Field(default=True, description="Is enabled")


class ToolCreate(ToolBase):
    """Create tool schema"""
    pass


class ToolUpdate(BaseModel):
    """Update tool schema"""
    display_name: Optional[str] = Field(None, description="Display name")
    description: Optional[str] = Field(None, description="Tool description")
    func_path: Optional[str] = Field(None, description="Function path")
    parameters: Optional[List[dict]] = Field(None, description="Parameter configuration")
    enabled: Optional[bool] = Field(None, description="Is enabled")


class ToolResponse(BaseModel):
    """Tool response schema"""
    id: int = Field(..., description="Tool ID")
    name: str = Field(..., description="Tool identifier")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Tool description")
    func_path: Optional[str] = Field(None, description="Function path")
    parameters: Optional[List[dict]] = Field(None, description="Parameter configuration")
    enabled: bool = Field(..., description="Is enabled")
    created_at: Optional[datetime] = Field(None, description="Created at")
    updated_at: Optional[datetime] = Field(None, description="Updated at")
    
    class Config:
        from_attributes = True
