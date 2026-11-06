"""
Skill schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class SkillBase(BaseModel):
    """Base skill schema"""
    name: str = Field(..., description="Skill name")
    description: Optional[str] = Field(None, description="Skill description")
    implementation: Optional[str] = Field(None, description="Skill content (Markdown format)")
    status: str = Field(default="active", description="Status: active/inactive")
    category_id: Optional[int] = Field(None, description="Skill category ID")


class SkillCreate(SkillBase):
    """Create skill schema"""
    tool_tag_ids: Optional[List[int]] = Field(None, description="List of tool tag IDs to bind")


class SkillUpdate(BaseModel):
    """Update skill schema"""
    name: Optional[str] = Field(None, description="Skill name")
    description: Optional[str] = Field(None, description="Skill description")
    implementation: Optional[str] = Field(None, description="Skill content (Markdown format)")
    status: Optional[str] = Field(None, description="Status: active/inactive")
    category_id: Optional[int] = Field(None, description="Skill category ID")
    tool_tag_ids: Optional[List[int]] = Field(None, description="List of tool tag IDs to bind")


class SkillResponse(BaseModel):
    """Skill response schema"""
    id: Optional[int] = Field(None, description="Skill ID")
    name: str = Field(..., description="Skill name")
    description: Optional[str] = Field(None, description="Skill description")
    implementation: Optional[str] = Field(None, description="Skill content (Markdown format)")
    status: str = Field(default="active", description="Status: active/inactive")
    category_id: Optional[int] = Field(None, description="Skill category ID")
    category_name: Optional[str] = Field(None, description="Skill category name")
    created_at: Optional[datetime] = Field(None, description="Created at")
    updated_at: Optional[datetime] = Field(None, description="Updated at")
    agent_count: int = Field(..., description="Number of agents using this skill")
    source: Optional[str] = Field("database", description="Skill source: database")
    bound_tools: List[str] = Field(default_factory=list, description="Tools bound to this skill")

    class Config:
        from_attributes = True


class SkillContentResponse(BaseModel):
    """Skill content response schema"""
    id: int = Field(..., description="Skill ID")
    name: str = Field(..., description="Skill name")
    content: str = Field(..., description="Skill content (Markdown format)")
