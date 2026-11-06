from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class FollowUpTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    lead_id: Optional[int] = Field(None, description="关联线索ID")
    opportunity_id: Optional[int] = Field(None, description="关联商机ID")
    assigned_to: int = Field(..., description="执行人ID")
    due_date: datetime = Field(..., description="截止时间")
    create_activity_on_complete: bool = Field(default=False, description="完成时是否创建活动记录")

    @model_validator(mode="after")
    def check_relation(self):
        if not self.lead_id and not self.opportunity_id:
            raise ValueError("线索ID和商机ID至少选一")
        return self


class FollowUpTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    status: Optional[str] = Field(None, description="任务状态")


class FollowUpTaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    assigned_to: int
    due_date: datetime
    status: str
    completed_at: Optional[datetime] = None
    create_activity_on_complete: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    status: Optional[str] = Field(None, description="任务状态过滤")
    assigned_to: Optional[int] = Field(None, description="执行人过滤")
    lead_id: Optional[int] = Field(None, description="线索ID过滤")
    opportunity_id: Optional[int] = Field(None, description="商机ID过滤")


class TaskCompleteRequest(BaseModel):
    create_activity: bool = Field(default=False, description="是否创建活动记录")
    activity_content: Optional[str] = Field(None, description="活动内容")