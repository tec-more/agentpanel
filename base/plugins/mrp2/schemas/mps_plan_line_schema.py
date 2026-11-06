from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field
from decimal import Decimal


class MPSPlanLineBase(BaseModel):
    mps_id: int = Field(..., description="MPS ID")
    mps_code: str = Field(..., max_length=100, description="MPS编号")
    line_no: int = Field(..., description="行号")
    product_code: str = Field(..., max_length=100, description="产品编码")
    product_name: str = Field(..., max_length=255, description="产品名称")
    plan_quantity: Decimal = Field(..., gt=0, description="计划数量")
    plan_start_date: date = Field(..., description="计划开始日期")
    plan_end_date: date = Field(..., description="计划结束日期")
    priority: int = Field(default=5, description="优先级(1-10)")
    sales_order_no: Optional[str] = Field(None, max_length=100, description="关联销售订单号")
    sales_order_line_no: Optional[int] = Field(None, description="关联销售订单行号")
    bom_code: Optional[str] = Field(None, max_length=100, description="BOM编码")
    route_code: Optional[str] = Field(None, max_length=100, description="工艺路线编码")
    remark: Optional[str] = Field(None, description="备注")


class MPSPlanLineCreate(MPSPlanLineBase):
    pass


class MPSPlanLineResponse(MPSPlanLineBase):
    id: int
    capacity_check_result: str = "pass"
    capacity_check_remark: Optional[str] = None
    actual_quantity: Decimal = Decimal("0")
    status: str = "planned"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MPSPlanLineListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mps_id: Optional[int] = Field(None, description="MPS ID")
    product_code: Optional[str] = Field(None, description="产品编码")
    status: Optional[str] = Field(None, description="状态")


class CompileMPSRequest(BaseModel):
    mps_id: int = Field(..., description="MPS ID")


class CapacityWarning(BaseModel):
    work_center_code: str
    work_center_name: str
    available_capacity: Decimal
    required_capacity: Decimal
    utilization: Decimal


class MPSCompileResponse(BaseModel):
    mps_id: int
    mps_code: str
    plan_lines: List[MPSPlanLineResponse] = []
    capacity_warnings: List[CapacityWarning] = []


class ApproveMPSRequest(BaseModel):
    approved: bool = Field(..., description="是否审核通过")
    remark: Optional[str] = Field(None, description="审核备注")


class MPSLineAdjustment(BaseModel):
    line_id: int = Field(..., description="计划行ID")
    plan_quantity: Optional[Decimal] = Field(None, description="调整后计划数量")
    plan_start_date: Optional[date] = Field(None, description="调整后开始日期")
    plan_end_date: Optional[date] = Field(None, description="调整后结束日期")
    priority: Optional[int] = Field(None, description="调整后优先级")
    remark: Optional[str] = Field(None, description="调整原因")


class MPSReleaseResponse(BaseModel):
    mps_id: int
    mps_code: str
    mrp_id: Optional[int] = None
    mrp_code: Optional[str] = None
    manufacturing_orders: List[dict] = Field(default_factory=list, description="生成的制造单列表")