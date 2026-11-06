from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    customer_id: int = Field(..., description="客户ID")
    name: str = Field(..., min_length=1, max_length=100, description="联系人姓名")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    position: Optional[str] = Field(None, max_length=100, description="职位")
    department: Optional[str] = Field(None, max_length=100, description="部门")
    is_primary: bool = Field(default=False, description="是否主联系人")
    remark: Optional[str] = Field(None, description="备注")


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="联系人姓名")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    position: Optional[str] = Field(None, max_length=100, description="职位")
    department: Optional[str] = Field(None, max_length=100, description="部门")
    is_primary: Optional[bool] = Field(None, description="是否主联系人")
    remark: Optional[str] = Field(None, description="备注")


class ContactResponse(BaseModel):
    id: int
    customer_id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    is_primary: bool
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    customer_id: Optional[int] = Field(None, description="客户ID过滤")
    keyword: Optional[str] = Field(None, description="关键词搜索(姓名/手机号)")