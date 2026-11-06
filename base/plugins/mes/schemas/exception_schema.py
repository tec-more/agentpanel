from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ProductionExceptionCreate(BaseModel):
    exception_type: str = Field(..., max_length=20, description="异常类型：equipment/material/quality/process/personnel")
    severity: str = Field(default="minor", max_length=20, description="严重程度：minor/major/critical")
    wo_code: Optional[str] = Field(None, max_length=100, description="关联工单编码")
    mo_code: Optional[str] = Field(None, max_length=100, description="关联制造单编码")
    work_center_code: str = Field(..., max_length=100, description="工作中心编码")
    description: str = Field(..., description="异常描述")
    reporter: str = Field(..., max_length=100, description="上报人")


class ProductionExceptionHandle(BaseModel):
    handler: str = Field(..., max_length=100, description="处理人")
    solution: str = Field(..., description="处理方案")


class ProductionExceptionResponse(BaseModel):
    id: int
    exception_code: str
    exception_type: str
    severity: str
    wo_code: Optional[str] = None
    mo_code: Optional[str] = None
    work_center_code: str
    description: str
    reporter: str
    status: str
    handler: Optional[str] = None
    solution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    escalation_level: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductionExceptionListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    exception_type: Optional[str] = Field(None, description="异常类型")
    severity: Optional[str] = Field(None, description="严重程度")
    status: Optional[str] = Field(None, description="状态")
    work_center_code: Optional[str] = Field(None, description="工作中心编码")