from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class OpportunityStageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="阶段名称")
    code: str = Field(..., min_length=1, max_length=50, description="阶段编码")
    sort_order: int = Field(default=0, description="排序")
    probability: Optional[int] = Field(None, ge=0, le=100, description="默认成交概率(%)")
    is_won_stage: bool = Field(default=False, description="是否赢单阶段")
    is_lost_stage: bool = Field(default=False, description="是否输单阶段")
    is_active: bool = Field(default=True, description="是否启用")


class OpportunityStageUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="阶段名称")
    sort_order: Optional[int] = Field(None, description="排序")
    probability: Optional[int] = Field(None, ge=0, le=100, description="默认成交概率(%)")
    is_won_stage: Optional[bool] = Field(None, description="是否赢单阶段")
    is_lost_stage: Optional[bool] = Field(None, description="是否输单阶段")
    is_active: Optional[bool] = Field(None, description="是否启用")


class OpportunityStageResponse(BaseModel):
    id: int
    name: str
    code: str
    sort_order: int
    probability: Optional[int] = None
    is_won_stage: bool
    is_lost_stage: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="来源名称")
    code: str = Field(..., min_length=1, max_length=50, description="来源编码")
    is_active: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=0, description="排序")


class LeadSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="来源名称")
    is_active: Optional[bool] = Field(None, description="是否启用")
    sort_order: Optional[int] = Field(None, description="排序")


class LeadSourceResponse(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CrmSettingsUpdate(BaseModel):
    auto_recycle_days: Optional[int] = Field(None, ge=1, description="自动回收天数")
    stale_warning_days: Optional[int] = Field(None, ge=1, description="超期预警天数")


class CrmSettingsResponse(BaseModel):
    auto_recycle_days: int
    stale_warning_days: int