from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class ProductionReportCreate(BaseModel):
    wo_code: str = Field(..., max_length=100, description="工单编码")
    mo_code: str = Field(..., max_length=100, description="制造单编码")
    process_code: str = Field(..., max_length=100, description="工序编码")
    work_center_code: str = Field(..., max_length=100, description="工作中心编码")
    operator: str = Field(..., max_length=100, description="操作员")
    shift_code: str = Field(..., max_length=100, description="班次编码")
    equipment_code: str = Field(..., max_length=100, description="设备编码")
    batch_no: str = Field(..., max_length=100, description="批次号")
    qualified_quantity: int = Field(..., ge=0, description="合格数量")
    scrap_quantity: int = Field(default=0, ge=0, description="报废数量")
    actual_start_time: datetime = Field(..., description="实际开始时间")
    actual_end_time: datetime = Field(..., description="实际结束时间")
    remark: Optional[str] = Field(None, description="备注")


class ProductionReportResponse(BaseModel):
    id: int
    report_code: str
    wo_code: str
    mo_code: str
    process_code: str
    work_center_code: str
    operator: str
    shift_code: str
    equipment_code: str
    batch_no: str
    qualified_quantity: int
    scrap_quantity: int
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    actual_work_hours: float = 0
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchReportRequest(BaseModel):
    reports: List[ProductionReportCreate] = Field(..., max_length=50, description="报工列表")


class BatchReportResponse(BaseModel):
    total: int = Field(..., description="总数")
    success_count: int = Field(..., description="成功数")
    fail_count: int = Field(..., description="失败数")
    results: List[ProductionReportResponse] = Field(default_factory=list, description="成功结果")


class ProductionReportListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    wo_code: Optional[str] = Field(None, description="工单编码")
    mo_code: Optional[str] = Field(None, description="制造单编码")
    operator: Optional[str] = Field(None, description="操作员")
    batch_no: Optional[str] = Field(None, description="批次号")
    work_center_code: Optional[str] = Field(None, description="工作中心编码")