"""
关注者 Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class FollowRequest(BaseModel):
    model: str = Field(..., max_length=100, description="业务表名")
    res_id: int = Field(..., description="业务记录ID")
    subtype_ids: Optional[List[int]] = Field(
        None, description="订阅的子类型ID列表（不传=订阅全部）"
    )


class UnfollowRequest(BaseModel):
    model: str = Field(..., max_length=100)
    res_id: int = Field(...)


class FollowerListQuery(BaseModel):
    model: str = Field(..., max_length=100)
    res_id: int = Field(...)
