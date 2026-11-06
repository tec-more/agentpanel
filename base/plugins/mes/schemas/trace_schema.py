from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class TraceForwardQuery(BaseModel):
    material_batch_no: str = Field(..., max_length=100, description="原材料批次号")


class TraceBackwardQuery(BaseModel):
    product_batch_no: str = Field(..., max_length=100, description="成品批次号")


class TraceRecordResponse(BaseModel):
    id: int
    trace_code: str
    product_batch_no: str
    material_batch_no: str
    mo_code: str
    wo_code: str
    process_code: str
    operator: str
    equipment_code: str
    work_center_code: str
    shift_code: str
    consumed_quantity: float
    produced_quantity: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True