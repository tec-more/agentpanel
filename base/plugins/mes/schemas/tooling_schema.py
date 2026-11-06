from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, Field


class ToolingCreate(BaseModel):
    tooling_code: str = Field(..., max_length=100, description="工装编码")
    tooling_name: str = Field(..., max_length=255, description="工装名称")
    tooling_type: str = Field(..., max_length=20, description="工装类型：mold/fixture/cutter/gauge")
    life_count: Optional[int] = Field(None, description="使用寿命(次数)")
    life_hours: Optional[float] = Field(None, description="使用寿命(小时)")
    calibration_date: Optional[date] = Field(None, description="上次校准日期")
    next_calibration_date: Optional[date] = Field(None, description="下次校准日期")
    work_center_code: Optional[str] = Field(None, max_length=100, description="所属工作中心编码")


class ToolingResponse(BaseModel):
    id: int
    tooling_code: str
    tooling_name: str
    tooling_type: str
    status: str
    life_count: Optional[int] = None
    used_count: int = 0
    life_hours: Optional[float] = None
    used_hours: float = 0
    calibration_date: Optional[date] = None
    next_calibration_date: Optional[date] = None
    work_center_code: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ToolingValidateRequest(BaseModel):
    tooling_code: str = Field(..., max_length=100, description="工装编码")


class ToolingValidateResponse(BaseModel):
    tooling_code: str
    is_valid: bool
    reason: Optional[str] = None


class ToolingListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    tooling_code: Optional[str] = Field(None, description="工装编码")
    tooling_type: Optional[str] = Field(None, description="工装类型")
    status: Optional[str] = Field(None, description="状态")
    work_center_code: Optional[str] = Field(None, description="工作中心编码")