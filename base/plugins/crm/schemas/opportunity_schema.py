from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field


class OpportunityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="商机名称")
    customer_id: int = Field(..., description="客户ID")
    contact_id: Optional[int] = Field(None, description="联系人ID")
    stage: str = Field(..., description="商机阶段code")
    expected_amount: Decimal = Field(..., gt=0, description="预期金额")
    probability: Optional[int] = Field(None, ge=0, le=100, description="成交概率(%)")
    expected_close_date: Optional[date] = Field(None, description="预计成交日期")
    assigned_to: Optional[int] = Field(None, description="负责人ID")
    product_id: Optional[int] = Field(None, description="关联产品ID")


class OpportunityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="商机名称")
    contact_id: Optional[int] = Field(None, description="联系人ID")
    expected_amount: Optional[Decimal] = Field(None, gt=0, description="预期金额")
    probability: Optional[int] = Field(None, ge=0, le=100, description="成交概率(%)")
    expected_close_date: Optional[date] = Field(None, description="预计成交日期")
    assigned_to: Optional[int] = Field(None, description="负责人ID")
    product_id: Optional[int] = Field(None, description="关联产品ID")


class OpportunityResponse(BaseModel):
    id: int
    name: str
    customer_id: int
    contact_id: Optional[int] = None
    stage: str
    expected_amount: Decimal
    actual_amount: Optional[Decimal] = None
    probability: Optional[int] = None
    expected_close_date: Optional[date] = None
    status: str
    lost_reason: Optional[str] = None
    assigned_to: Optional[int] = None
    last_follow_up_time: Optional[datetime] = None
    won_at: Optional[datetime] = None
    lost_at: Optional[datetime] = None
    product_id: Optional[int] = None
    order_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OpportunityListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    status: Optional[str] = Field(None, description="商机状态过滤")
    stage: Optional[str] = Field(None, description="商机阶段过滤")
    assigned_to: Optional[int] = Field(None, description="负责人过滤")
    customer_id: Optional[int] = Field(None, description="客户ID过滤")


class OpportunityAdvanceRequest(BaseModel):
    to_stage: str = Field(..., description="目标阶段code")
    remark: Optional[str] = Field(None, description="备注")


class OpportunityWinRequest(BaseModel):
    actual_amount: Decimal = Field(..., gt=0, description="成交金额")
    create_order: bool = Field(default=False, description="是否创建订单")


class OpportunityLoseRequest(BaseModel):
    lost_reason: str = Field(..., min_length=1, description="输单原因")


class KanbanItem(BaseModel):
    id: int
    name: str
    customer_id: int
    expected_amount: Decimal
    probability: Optional[int] = None
    assigned_to: Optional[int] = None
    expected_close_date: Optional[date] = None

    class Config:
        from_attributes = True


class KanbanResponse(BaseModel):
    stage_code: str
    stage_name: str
    opportunities: List[KanbanItem]