from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class LeadCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="线索姓名")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    company: Optional[str] = Field(None, max_length=200, description="公司名称")
    source: Optional[str] = Field(None, max_length=50, description="线索来源")
    description: Optional[str] = Field(None, description="描述")
    assigned_to: Optional[int] = Field(None, description="负责人ID")

    @model_validator(mode="after")
    def check_contact(self):
        if not self.phone and not self.email:
            raise ValueError("手机号和邮箱至少填写一个")
        return self


class LeadUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="线索姓名")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    company: Optional[str] = Field(None, max_length=200, description="公司名称")
    source: Optional[str] = Field(None, max_length=50, description="线索来源")
    description: Optional[str] = Field(None, description="描述")
    assigned_to: Optional[int] = Field(None, description="负责人ID")


class LeadResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    status: str
    assigned_to: Optional[int] = None
    customer_id: Optional[int] = None
    description: Optional[str] = None
    last_follow_up_time: Optional[datetime] = None
    converted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    status: Optional[str] = Field(None, description="线索状态过滤")
    source: Optional[str] = Field(None, description="线索来源过滤")
    assigned_to: Optional[int] = Field(None, description="负责人过滤")
    keyword: Optional[str] = Field(None, description="关键词搜索(姓名/公司)")


class LeadConvertRequest(BaseModel):
    pass


class LeadAssignRequest(BaseModel):
    assigned_to: int = Field(..., description="负责人ID")