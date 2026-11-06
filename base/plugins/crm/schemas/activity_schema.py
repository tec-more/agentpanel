from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class ActivityCreate(BaseModel):
    type: str = Field(..., description="活动类型(call/meeting/email/visit/other)")
    subject: str = Field(..., min_length=1, max_length=200, description="主题")
    content: Optional[str] = Field(None, description="内容")
    activity_time: datetime = Field(..., description="活动时间")
    lead_id: Optional[int] = Field(None, description="关联线索ID")
    opportunity_id: Optional[int] = Field(None, description="关联商机ID")
    contact_id: Optional[int] = Field(None, description="关联联系人ID")

    @model_validator(mode="after")
    def check_relation(self):
        if not self.lead_id and not self.opportunity_id:
            raise ValueError("线索ID和商机ID至少选一")
        return self


class ActivityResponse(BaseModel):
    id: int
    type: str
    subject: str
    content: Optional[str] = None
    activity_time: datetime
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    contact_id: Optional[int] = None
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    lead_id: Optional[int] = Field(None, description="线索ID过滤")
    opportunity_id: Optional[int] = Field(None, description="商机ID过滤")
    type: Optional[str] = Field(None, description="活动类型过滤")


class TimelineQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=200, description="每页数量")
    lead_id: Optional[int] = Field(None, description="线索ID")
    opportunity_id: Optional[int] = Field(None, description="商机ID")