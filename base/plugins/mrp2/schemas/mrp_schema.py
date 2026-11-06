from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal


class SalesForecastBase(BaseModel):
    forecast_code: str = Field(..., min_length=1, max_length=100, description="预测编号")
    forecast_name: str = Field(..., min_length=1, max_length=255, description="预测名称")
    forecast_type: str = Field(default="monthly", max_length=20, description="预测类型：monthly/quarterly/yearly")
    forecast_date: date = Field(..., description="预测日期")
    start_date: date = Field(..., description="预测开始日期")
    end_date: date = Field(..., description="预测结束日期")
    status: str = Field(default="draft", max_length=20, description="状态：draft/review/approved/executed")
    source: str = Field(default="manual", max_length=50, description="预测来源：manual/history/market")
    description: Optional[str] = Field(None, description="描述")
    created_by: Optional[str] = Field(None, max_length=100, description="创建人")


class SalesForecastCreate(SalesForecastBase):
    pass


class SalesForecastUpdate(BaseModel):
    forecast_code: Optional[str] = Field(None, min_length=1, max_length=100, description="预测编号")
    forecast_name: Optional[str] = Field(None, min_length=1, max_length=255, description="预测名称")
    forecast_type: Optional[str] = Field(None, max_length=20, description="预测类型")
    forecast_date: Optional[date] = Field(None, description="预测日期")
    start_date: Optional[date] = Field(None, description="预测开始日期")
    end_date: Optional[date] = Field(None, description="预测结束日期")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    source: Optional[str] = Field(None, max_length=50, description="预测来源")
    description: Optional[str] = Field(None, description="描述")


class SalesForecastResponse(SalesForecastBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SalesForecastDetailBase(BaseModel):
    forecast_id: int = Field(..., description="预测ID")
    product_id: Optional[int] = Field(None, description="产品ID")
    product_code: str = Field(..., min_length=1, max_length=100, description="产品编码")
    product_name: str = Field(..., min_length=1, max_length=255, description="产品名称")
    period_type: str = Field(default="month", max_length=20, description="周期类型：week/month/quarter")
    period_start: date = Field(..., description="周期开始日期")
    period_end: date = Field(..., description="周期结束日期")
    forecast_quantity: Decimal = Field(..., ge=Decimal("0"), max_digits=15, decimal_places=6, description="预测数量")
    unit: str = Field(..., max_length=20, description="计量单位")
    confidence: Decimal = Field(default=80, ge=0, le=100, max_digits=5, decimal_places=2, description="置信度(%)")
    remark: Optional[str] = Field(None, description="备注")


class SalesForecastDetailCreate(SalesForecastDetailBase):
    pass


class SalesForecastDetailResponse(SalesForecastDetailBase):
    id: int
    forecast_code: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SalesForecastListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    forecast_code: Optional[str] = Field(None, description="预测编号")
    forecast_name: Optional[str] = Field(None, description="预测名称")
    forecast_type: Optional[str] = Field(None, description="预测类型")
    status: Optional[str] = Field(None, description="状态")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")


class MasterProductionScheduleBase(BaseModel):
    mps_code: str = Field(..., min_length=1, max_length=100, description="MPS编号")
    mps_name: str = Field(..., min_length=1, max_length=255, description="MPS名称")
    start_date: date = Field(..., description="计划开始日期")
    end_date: date = Field(..., description="计划结束日期")
    period_type: str = Field(default="week", max_length=20, description="计划周期：week/month")
    status: str = Field(default="draft", max_length=20, description="状态：draft/review/approved/released/executed")
    forecast_id: Optional[int] = Field(None, description="关联销售预测ID")
    forecast_code: Optional[str] = Field(None, max_length=100, description="关联销售预测编号")
    description: Optional[str] = Field(None, description="描述")
    created_by: Optional[str] = Field(None, max_length=100, description="创建人")


class MPSCreate(MasterProductionScheduleBase):
    pass


class MPSUpdate(BaseModel):
    mps_code: Optional[str] = Field(None, min_length=1, max_length=100, description="MPS编号")
    mps_name: Optional[str] = Field(None, min_length=1, max_length=255, description="MPS名称")
    start_date: Optional[date] = Field(None, description="计划开始日期")
    end_date: Optional[date] = Field(None, description="计划结束日期")
    period_type: Optional[str] = Field(None, max_length=20, description="计划周期")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    forecast_id: Optional[int] = Field(None, description="关联销售预测ID")
    forecast_code: Optional[str] = Field(None, max_length=100, description="关联销售预测编号")
    description: Optional[str] = Field(None, description="描述")


class MPSResponse(MasterProductionScheduleBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MPSDetailBase(BaseModel):
    mps_id: int = Field(..., description="MPS ID")
    product_id: Optional[int] = Field(None, description="产品ID")
    product_code: str = Field(..., min_length=1, max_length=100, description="产品编码")
    product_name: str = Field(..., min_length=1, max_length=255, description="产品名称")
    bom_version: Optional[str] = Field(None, max_length=20, description="BOM版本")
    route_code: Optional[str] = Field(None, max_length=100, description="工艺路线编码")
    period_start: date = Field(..., description="周期开始日期")
    period_end: date = Field(..., description="周期结束日期")
    forecast_quantity: Decimal = Field(default=0, ge=0, max_digits=15, decimal_places=6, description="预测数量")
    planned_quantity: Decimal = Field(..., ge=0, max_digits=15, decimal_places=6, description="计划数量")
    unit: str = Field(..., max_length=20, description="计量单位")
    safety_stock: Decimal = Field(default=0, ge=0, max_digits=15, decimal_places=6, description="安全库存")
    remark: Optional[str] = Field(None, description="备注")


class MPSDetailCreate(MPSDetailBase):
    pass


class MPSDetailResponse(MPSDetailBase):
    id: int
    mps_code: Optional[str] = None
    production_quantity: Decimal = 0
    planned_inventory: Decimal = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MPSListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mps_code: Optional[str] = Field(None, description="MPS编号")
    mps_name: Optional[str] = Field(None, description="MPS名称")
    status: Optional[str] = Field(None, description="状态")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")


class MRPCalculationBase(BaseModel):
    mrp_code: str = Field(..., min_length=1, max_length=100, description="MRP编号")
    mrp_name: str = Field(..., min_length=1, max_length=255, description="MRP名称")
    mps_id: Optional[int] = Field(None, description="关联MPS ID")
    mps_code: Optional[str] = Field(None, max_length=100, description="关联MPS编号")
    start_date: date = Field(..., description="需求开始日期")
    end_date: date = Field(..., description="需求结束日期")
    net_requirement_only: bool = Field(default=False, description="是否仅计算净需求")
    include_safety_stock: bool = Field(default=True, description="是否包含安全库存")
    include_wip: bool = Field(default=True, description="是否包含在制品")
    created_by: Optional[str] = Field(None, max_length=100, description="创建人")


class MRPCalculationCreate(MRPCalculationBase):
    pass


class MRPCalculationResponse(MRPCalculationBase):
    id: int
    calculation_date: Optional[datetime] = None
    status: str = "calculating"
    calculation_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MRPResultDetailResponse(BaseModel):
    id: int
    mrp_id: int
    mrp_code: str
    level: int = 1
    product_id: Optional[int] = None
    product_code: str
    product_name: str
    period_start: date
    period_end: date
    gross_requirement: Decimal = 0
    scheduled_receipts: Decimal = 0
    projected_available: Decimal = 0
    net_requirement: Decimal = 0
    planned_order_receipt: Decimal = 0
    planned_order_release: Decimal = 0
    planned_release_date: Optional[date] = None
    planned_receipt_date: Optional[date] = None
    lot_size: Decimal = 1
    lead_time: int = 0
    safety_stock: Decimal = 0
    unit: str
    parent_item_code: Optional[str] = None
    bom_quantity: Decimal = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MRPListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mrp_code: Optional[str] = Field(None, description="MRP编号")
    mrp_name: Optional[str] = Field(None, description="MRP名称")
    status: Optional[str] = Field(None, description="状态")
    mps_code: Optional[str] = Field(None, description="关联MPS编号")


class CapacityRequirementPlanBase(BaseModel):
    crp_code: str = Field(..., min_length=1, max_length=100, description="CRP编号")
    crp_name: str = Field(..., min_length=1, max_length=255, description="CRP名称")
    mrp_id: Optional[int] = Field(None, description="关联MRP ID")
    mrp_code: Optional[str] = Field(None, max_length=100, description="关联MRP编号")
    mps_id: Optional[int] = Field(None, description="关联MPS ID")
    mps_code: Optional[str] = Field(None, max_length=100, description="关联MPS编号")
    start_date: date = Field(..., description="计划开始日期")
    end_date: date = Field(..., description="计划结束日期")
    created_by: Optional[str] = Field(None, max_length=100, description="创建人")


class CRPCreate(CapacityRequirementPlanBase):
    pass


class CRPResponse(CapacityRequirementPlanBase):
    id: int
    status: str = "calculating"
    calculation_date: Optional[datetime] = None
    overall_capacity_utilization: Decimal = 0
    bottleneck_work_centers: Optional[List[Dict[str, Any]]] = None
    calculation_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CRPDetailResponse(BaseModel):
    id: int
    crp_id: int
    crp_code: str
    work_center_code: str
    work_center_name: str
    period_start: date
    period_end: date
    available_capacity: Decimal = 0
    required_capacity: Decimal = 0
    utilized_capacity: Decimal = 0
    capacity_utilization: Decimal = 0
    is_overloaded: bool = False
    overload_hours: Decimal = 0
    recommended_action: Optional[str] = None
    detail_items: Optional[List[Dict[str, Any]]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CRPListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    crp_code: Optional[str] = Field(None, description="CRP编号")
    crp_name: Optional[str] = Field(None, description="CRP名称")
    status: Optional[str] = Field(None, description="状态")


class PlanExecutionMonitorBase(BaseModel):
    monitor_code: str = Field(..., min_length=1, max_length=100, description="监控编号")
    monitor_name: str = Field(..., min_length=1, max_length=255, description="监控名称")
    mps_id: Optional[int] = Field(None, description="关联MPS ID")
    mps_code: Optional[str] = Field(None, max_length=100, description="关联MPS编号")
    mrp_id: Optional[int] = Field(None, description="关联MRP ID")
    mrp_code: Optional[str] = Field(None, max_length=100, description="关联MRP编号")
    start_date: date = Field(..., description="监控开始日期")
    end_date: date = Field(..., description="监控结束日期")
    created_by: Optional[str] = Field(None, max_length=100, description="创建人")


class MonitorCreate(PlanExecutionMonitorBase):
    pass


class MonitorResponse(PlanExecutionMonitorBase):
    id: int
    status: str = "monitoring"
    overall_progress: Decimal = 0
    on_time_rate: Decimal = 0
    quality_rate: Decimal = 0
    efficiency_rate: Decimal = 0
    alert_count: int = 0
    exception_count: int = 0
    metrics_summary: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MonitorListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    monitor_code: Optional[str] = Field(None, description="监控编号")
    monitor_name: Optional[str] = Field(None, description="监控名称")
    status: Optional[str] = Field(None, description="状态")


class MRPExceptionAlertBase(BaseModel):
    alert_code: str = Field(..., min_length=1, max_length=100, description="告警编号")
    monitor_id: Optional[int] = Field(None, description="关联监控ID")
    alert_type: str = Field(..., max_length=50, description="告警类型：material_shortage/capacity_overload/delay/due_date")
    alert_level: str = Field(default="warning", max_length=20, description="告警级别：info/warning/critical")
    alert_status: str = Field(default="active", max_length=20, description="告警状态：active/resolved")
    related_code: Optional[str] = Field(None, max_length=100, description="关联编号")
    related_name: Optional[str] = Field(None, max_length=255, description="关联名称")
    description: str = Field(..., description="告警描述")
    recommended_action: Optional[str] = Field(None, description="建议措施")


class AlertCreate(MRPExceptionAlertBase):
    pass


class AlertResponse(MRPExceptionAlertBase):
    id: int
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    alert_code: Optional[str] = Field(None, description="告警编号")
    alert_type: Optional[str] = Field(None, description="告警类型")
    alert_level: Optional[str] = Field(None, description="告警级别")
    alert_status: Optional[str] = Field(None, description="告警状态")


class MRPCalculateRequest(BaseModel):
    mps_id: Optional[int] = Field(None, description="MPS ID")
    mps_code: Optional[str] = Field(None, description="MPS编号")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    net_requirement_only: bool = Field(default=False, description="是否仅计算净需求")
    include_safety_stock: bool = Field(default=True, description="是否包含安全库存")
    include_wip: bool = Field(default=True, description="是否包含在制品")


class CRPCalculateRequest(BaseModel):
    mrp_id: Optional[int] = Field(None, description="MRP ID")
    mrp_code: Optional[str] = Field(None, description="MRP编号")
    mps_id: Optional[int] = Field(None, description="MPS ID")
    mps_code: Optional[str] = Field(None, description="MPS编号")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[T] = Field(..., description="数据列表")