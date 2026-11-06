"""
Skill Category schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class SkillCategoryBase(BaseModel):
    """Base skill category schema"""
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    parent_id: Optional[int] = Field(None, description="Parent category ID")
    sort_order: int = Field(default=0, description="Sort order")
    status: str = Field(default="active", description="Status: active/inactive")


class SkillCategoryCreate(SkillCategoryBase):
    """Create skill category schema"""
    pass


class SkillCategoryUpdate(BaseModel):
    """Update skill category schema"""
    name: Optional[str] = Field(None, description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    parent_id: Optional[int] = Field(None, description="Parent category ID")
    sort_order: Optional[int] = Field(None, description="Sort order")
    status: Optional[str] = Field(None, description="Status: active/inactive")


class SkillCategoryResponse(BaseModel):
    """Skill category response schema"""
    id: int = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    parent_id: Optional[int] = Field(None, description="Parent category ID")
    parent_name: Optional[str] = Field(None, description="Parent category name")
    sort_order: int = Field(default=0, description="Sort order")
    status: str = Field(default="active", description="Status: active/inactive")
    skill_count: int = Field(0, description="Number of skills in this category")
    created_at: Optional[datetime] = Field(None, description="Created at")
    updated_at: Optional[datetime] = Field(None, description="Updated at")
    
    class Config:
        from_attributes = True


class SkillCategoryTreeResponse(BaseModel):
    """Skill category tree response schema"""
    id: int = Field(..., description="Category ID")
    name: str = Field(..., description="Category name")
    description: Optional[str] = Field(None, description="Category description")
    sort_order: int = Field(default=0, description="Sort order")
    status: str = Field(default="active", description="Status: active/inactive")
    skill_count: int = Field(0, description="Number of skills in this category")
    children: List['SkillCategoryTreeResponse'] = Field(default_factory=list, description="Child categories")
    
    class Config:
        from_attributes = True


SkillCategoryTreeResponse.update_forward_refs()
