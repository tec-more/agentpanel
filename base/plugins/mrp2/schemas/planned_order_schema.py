from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field
from decimal import Decimal


class PlannedOrderResponse(BaseModel):
    id: int
    order_code: str
    mrp_id: Optional[int] = None
    mrp_code: Optional[str] = None
    order_type: str
    material_code: str
    material_name: str
    net_quantity: Decimal
    plan_quantity: Decimal
    unit: str
    require_date: Optional[date] = None
    plan_release_date: Optional[date] = None
    lead_time: int = 0
    batch_rule: str = "lot_for_lot"
    batch_size: Decimal = Decimal("1")
    safety_stock: Decimal = Decimal("0")
    current_stock: Decimal = Decimal("0")
    on_order_quantity: Decimal = Decimal("0")
    gross_requirement: Decimal = Decimal("0")
    net_requirement: Decimal = Decimal("0")
    bom_level: int = 0
    parent_material_code: Optional[str] = None
    status: str = "planned"
    source_mps_id: Optional[int] = None
    source_mps_line_id: Optional[int] = None
    converted_mo_code: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlannedOrderConfirmRequest(BaseModel):
    remark: Optional[str] = Field(None, description="确认备注")


class PlannedOrderListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mrp_id: Optional[int] = Field(None, description="MRP计算ID")
    order_type: Optional[str] = Field(None, description="订单类型")
    material_code: Optional[str] = Field(None, description="物料编码")
    status: Optional[str] = Field(None, description="状态")