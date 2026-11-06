from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, computed_field
from decimal import Decimal


class MaterialBase(BaseModel):
    product_id: Optional[int] = Field(None, description="产品ID")
    material_code: str = Field(..., min_length=1, max_length=100, description="物料编码")
    material_name: str = Field(..., min_length=1, max_length=255, description="物料名称")
    material_type: str = Field(..., max_length=50, description="物料类型：raw/finished/semi/fixture")
    unit: str = Field(..., max_length=20, description="计量单位")
    specification: Optional[str] = Field(None, max_length=255, description="规格型号")
    description: Optional[str] = Field(None, description="物料描述")
    initial_stock: int = Field(default=0, ge=0, description="初始库存数量")
    is_active: bool = Field(default=True, description="是否启用")


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    material_code: Optional[str] = Field(None, min_length=1, max_length=100, description="物料编码")
    material_name: Optional[str] = Field(None, min_length=1, max_length=255, description="物料名称")
    material_type: Optional[str] = Field(None, max_length=50, description="物料类型")
    unit: Optional[str] = Field(None, max_length=20, description="计量单位")
    specification: Optional[str] = Field(None, max_length=255, description="规格型号")
    description: Optional[str] = Field(None, description="物料描述")
    initial_stock: Optional[int] = Field(None, ge=0, description="初始库存数量")
    is_active: Optional[bool] = Field(None, description="是否启用")


class MaterialResponse(MaterialBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaterialListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    material_code: Optional[str] = Field(None, description="物料编码")
    material_name: Optional[str] = Field(None, description="物料名称")
    material_type: Optional[str] = Field(None, description="物料类型")
    is_active: Optional[bool] = Field(None, description="是否启用")


class BomBase(BaseModel):
    product_id: Optional[int] = Field(None, description="成品产品ID")
    product_code: str = Field(..., min_length=1, max_length=100, description="成品编码")
    product_name: str = Field(..., min_length=1, max_length=255, description="成品名称")
    version: str = Field(default="V1.0", max_length=20, description="版本号")
    level: int = Field(default=1, ge=1, description="BOM层级")
    parent_item_code: Optional[str] = Field(None, max_length=100, description="父项编码")
    item_id: Optional[int] = Field(None, description="物料产品ID")
    item_code: str = Field(..., min_length=1, max_length=100, description="物料编码")
    item_name: str = Field(..., min_length=1, max_length=255, description="物料名称")
    quantity: Decimal = Field(..., ge=Decimal("0.000001"), max_digits=15, decimal_places=6, description="用量")
    unit: str = Field(..., max_length=20, description="计量单位")
    scrap_rate: Decimal = Field(default=Decimal("0"), max_digits=5, decimal_places=4, description="损耗率")
    remark: Optional[str] = Field(None, description="备注")
    is_active: bool = Field(default=True, description="是否启用")


class BomCreate(BomBase):
    pass


class BomUpdate(BaseModel):
    product_code: Optional[str] = Field(None, min_length=1, max_length=100, description="成品编码")
    product_name: Optional[str] = Field(None, min_length=1, max_length=255, description="成品名称")
    version: Optional[str] = Field(None, max_length=20, description="版本号")
    level: Optional[int] = Field(None, ge=1, description="BOM层级")
    parent_item_code: Optional[str] = Field(None, max_length=100, description="父项编码")
    item_code: Optional[str] = Field(None, min_length=1, max_length=100, description="物料编码")
    item_name: Optional[str] = Field(None, min_length=1, max_length=255, description="物料名称")
    quantity: Optional[Decimal] = Field(None, ge=Decimal("0.000001"), max_digits=15, decimal_places=6, description="用量")
    unit: Optional[str] = Field(None, max_length=20, description="计量单位")
    scrap_rate: Optional[Decimal] = Field(None, max_digits=5, decimal_places=4, description="损耗率")
    remark: Optional[str] = Field(None, description="备注")
    is_active: Optional[bool] = Field(None, description="是否启用")


class BomResponse(BomBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BomListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    product_code: Optional[str] = Field(None, description="成品编码")
    item_code: Optional[str] = Field(None, description="物料编码")
    version: Optional[str] = Field(None, description="版本号")


class WorkCenterBase(BaseModel):
    work_center_code: str = Field(..., min_length=1, max_length=100, description="工作中心编码")
    work_center_name: str = Field(..., min_length=1, max_length=255, description="工作中心名称")
    department: Optional[str] = Field(None, max_length=100, description="所属部门")
    location: Optional[str] = Field(None, max_length=255, description="位置")
    capacity: int = Field(default=1, ge=1, description="产能")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = Field(default=True, description="是否启用")


class WorkCenterCreate(WorkCenterBase):
    pass


class WorkCenterUpdate(BaseModel):
    work_center_code: Optional[str] = Field(None, min_length=1, max_length=100, description="工作中心编码")
    work_center_name: Optional[str] = Field(None, min_length=1, max_length=255, description="工作中心名称")
    department: Optional[str] = Field(None, max_length=100, description="所属部门")
    location: Optional[str] = Field(None, max_length=255, description="位置")
    capacity: Optional[int] = Field(None, ge=1, description="产能")
    description: Optional[str] = Field(None, description="描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class WorkCenterResponse(WorkCenterBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkCenterListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    work_center_code: Optional[str] = Field(None, description="工作中心编码")
    work_center_name: Optional[str] = Field(None, description="工作中心名称")
    department: Optional[str] = Field(None, description="所属部门")


class ProcessBase(BaseModel):
    process_code: str = Field(..., min_length=1, max_length=100, description="工序编码")
    process_name: str = Field(..., min_length=1, max_length=255, description="工序名称")
    process_type: str = Field(..., max_length=50, description="工艺类型")
    sequence: int = Field(default=0, ge=0, description="工序顺序")
    work_center_code: Optional[str] = Field(None, max_length=100, description="工作中心编码")
    work_center_name: Optional[str] = Field(None, max_length=255, description="工作中心名称")
    standard_time: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2, description="标准工时(分钟)")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = Field(default=True, description="是否启用")


class ProcessCreate(ProcessBase):
    pass


class ProcessUpdate(BaseModel):
    process_code: Optional[str] = Field(None, min_length=1, max_length=100, description="工序编码")
    process_name: Optional[str] = Field(None, min_length=1, max_length=255, description="工序名称")
    process_type: Optional[str] = Field(None, max_length=50, description="工艺类型")
    sequence: Optional[int] = Field(None, ge=0, description="工序顺序")
    work_center_code: Optional[str] = Field(None, max_length=100, description="工作中心编码")
    work_center_name: Optional[str] = Field(None, max_length=255, description="工作中心名称")
    standard_time: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2, description="标准工时")
    description: Optional[str] = Field(None, description="描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class ProcessResponse(ProcessBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProcessListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    process_code: Optional[str] = Field(None, description="工序编码")
    process_name: Optional[str] = Field(None, description="工序名称")
    work_center_code: Optional[str] = Field(None, description="工作中心编码")


class RouteBase(BaseModel):
    route_code: str = Field(..., min_length=1, max_length=100, description="路线编码")
    route_name: str = Field(..., min_length=1, max_length=255, description="路线名称")
    product_code: str = Field(..., min_length=1, max_length=100, description="产品编码")
    product_name: str = Field(..., min_length=1, max_length=255, description="产品名称")
    version: str = Field(default="V1.0", max_length=20, description="版本号")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = Field(default=True, description="是否启用")


class RouteCreate(RouteBase):
    pass


class RouteUpdate(BaseModel):
    route_code: Optional[str] = Field(None, min_length=1, max_length=100, description="路线编码")
    route_name: Optional[str] = Field(None, min_length=1, max_length=255, description="路线名称")
    product_code: Optional[str] = Field(None, min_length=1, max_length=100, description="产品编码")
    product_name: Optional[str] = Field(None, min_length=1, max_length=255, description="产品名称")
    version: Optional[str] = Field(None, max_length=20, description="版本号")
    description: Optional[str] = Field(None, description="描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class RouteResponse(RouteBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RouteListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    route_code: Optional[str] = Field(None, description="路线编码")
    route_name: Optional[str] = Field(None, description="路线名称")
    product_code: Optional[str] = Field(None, description="产品编码")


class ManufacturingOrderBase(BaseModel):
    mo_code: str = Field(..., min_length=1, max_length=100, description="制造单编码")
    product_code: str = Field(..., min_length=1, max_length=100, description="产品编码")
    product_name: str = Field(..., min_length=1, max_length=255, description="产品名称")
    quantity: int = Field(..., ge=1, description="计划数量")
    status: str = Field(default="planned", max_length=20, description="状态：planned/released/processing/completed/canceled")
    priority: str = Field(default="normal", max_length=20, description="优先级：low/normal/high/urgent")
    route_code: Optional[str] = Field(None, max_length=100, description="生产路线编码")
    bom_version: Optional[str] = Field(None, max_length=20, description="BOM版本")
    planned_start_date: Optional[datetime] = Field(None, description="计划开始日期")
    planned_end_date: Optional[datetime] = Field(None, description="计划结束日期")
    remark: Optional[str] = Field(None, description="备注")


class ManufacturingOrderCreate(ManufacturingOrderBase):
    pass


class ManufacturingOrderUpdate(BaseModel):
    mo_code: Optional[str] = Field(None, min_length=1, max_length=100, description="制造单编码")
    product_code: Optional[str] = Field(None, min_length=1, max_length=100, description="产品编码")
    product_name: Optional[str] = Field(None, min_length=1, max_length=255, description="产品名称")
    quantity: Optional[int] = Field(None, ge=1, description="计划数量")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    priority: Optional[str] = Field(None, max_length=20, description="优先级")
    route_code: Optional[str] = Field(None, max_length=100, description="生产路线编码")
    bom_version: Optional[str] = Field(None, max_length=20, description="BOM版本")
    planned_start_date: Optional[datetime] = Field(None, description="计划开始日期")
    planned_end_date: Optional[datetime] = Field(None, description="计划结束日期")
    remark: Optional[str] = Field(None, description="备注")


class ManufacturingOrderResponse(ManufacturingOrderBase):
    id: int
    actual_quantity: int = 0
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ManufacturingOrderListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mo_code: Optional[str] = Field(None, description="制造单编码")
    product_code: Optional[str] = Field(None, description="产品编码")
    status: Optional[str] = Field(None, description="状态")
    priority: Optional[str] = Field(None, description="优先级")


class WorkOrderBase(BaseModel):
    wo_code: str = Field(..., min_length=1, max_length=100, description="工单编码")
    mo_code: str = Field(..., min_length=1, max_length=100, description="制造单编码")
    mo_name: Optional[str] = Field(None, max_length=255, description="制造单名称")
    product_code: str = Field(..., min_length=1, max_length=100, description="产品编码")
    product_name: str = Field(..., min_length=1, max_length=255, description="产品名称")
    process_code: str = Field(..., min_length=1, max_length=100, description="工序编码")
    process_name: str = Field(..., min_length=1, max_length=255, description="工序名称")
    work_center_code: Optional[str] = Field(None, max_length=100, description="工作中心编码")
    work_center_name: Optional[str] = Field(None, max_length=255, description="工作中心名称")
    quantity: int = Field(..., ge=1, description="计划数量")
    status: str = Field(default="pending", max_length=20, description="状态：pending/released/processing/completed/closed")
    operator: Optional[str] = Field(None, max_length=100, description="操作员")
    planned_start_date: Optional[datetime] = Field(None, description="计划开始日期")
    planned_end_date: Optional[datetime] = Field(None, description="计划结束日期")
    remark: Optional[str] = Field(None, description="备注")


class WorkOrderCreate(WorkOrderBase):
    pass


class WorkOrderUpdate(BaseModel):
    wo_code: Optional[str] = Field(None, min_length=1, max_length=100, description="工单编码")
    mo_code: Optional[str] = Field(None, min_length=1, max_length=100, description="制造单编码")
    product_code: Optional[str] = Field(None, min_length=1, max_length=100, description="产品编码")
    process_code: Optional[str] = Field(None, min_length=1, max_length=100, description="工序编码")
    work_center_code: Optional[str] = Field(None, min_length=1, max_length=100, description="工作中心编码")
    quantity: Optional[int] = Field(None, ge=1, description="计划数量")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    operator: Optional[str] = Field(None, max_length=100, description="操作员")
    remark: Optional[str] = Field(None, description="备注")


class WorkOrderResponse(WorkOrderBase):
    id: int
    actual_quantity: int = 0
    scrap_quantity: int = 0
    actual_start_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkOrderListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    wo_code: Optional[str] = Field(None, description="工单编码")
    mo_code: Optional[str] = Field(None, description="制造单编码")
    product_code: Optional[str] = Field(None, description="产品编码")
    status: Optional[str] = Field(None, description="状态")
    work_center_code: Optional[str] = Field(None, description="工作中心编码")


class QualityInspectionBase(BaseModel):
    inspection_code: str = Field(..., min_length=1, max_length=100, description="检验单号")
    inspection_type: str = Field(..., max_length=20, description="检验类型：IQC/IPQC/FQC/OQC")
    mo_code: Optional[str] = Field(None, max_length=100, description="制造单编码")
    wo_code: Optional[str] = Field(None, max_length=100, description="工单编码")
    material_code: str = Field(..., min_length=1, max_length=100, description="物料编码")
    material_name: str = Field(..., min_length=1, max_length=255, description="物料名称")
    batch_no: Optional[str] = Field(None, max_length=100, description="批次号")
    quantity: int = Field(..., ge=1, description="检验数量")
    inspection_result: str = Field(default="pending", max_length=20, description="检验结果：pending/qualified/unqualified")
    inspector: Optional[str] = Field(None, max_length=100, description="检验员")
    inspection_items: Optional[List[Dict[str, Any]]] = Field(None, description="检验项目及结果")
    remark: Optional[str] = Field(None, description="备注")


class QualityInspectionCreate(QualityInspectionBase):
    pass


class QualityInspectionUpdate(BaseModel):
    qualified_quantity: Optional[int] = Field(None, ge=0, description="合格数量")
    unqualified_quantity: Optional[int] = Field(None, ge=0, description="不合格数量")
    inspection_result: Optional[str] = Field(None, max_length=20, description="检验结果")
    inspector: Optional[str] = Field(None, max_length=100, description="检验员")
    inspection_items: Optional[List[Dict[str, Any]]] = Field(None, description="检验项目及结果")
    remark: Optional[str] = Field(None, description="备注")


class QualityInspectionResponse(QualityInspectionBase):
    id: int
    qualified_quantity: int = 0
    unqualified_quantity: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QualityInspectionListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    inspection_code: Optional[str] = Field(None, description="检验单号")
    inspection_type: Optional[str] = Field(None, description="检验类型")
    material_code: Optional[str] = Field(None, description="物料编码")
    inspection_result: Optional[str] = Field(None, description="检验结果")


class EquipmentBase(BaseModel):
    equipment_code: str = Field(..., min_length=1, max_length=100, description="设备编码")
    equipment_name: str = Field(..., min_length=1, max_length=255, description="设备名称")
    equipment_type: str = Field(..., max_length=50, description="设备类型")
    model: Optional[str] = Field(None, max_length=100, description="设备型号")
    manufacturer: Optional[str] = Field(None, max_length=255, description="制造商")
    location: Optional[str] = Field(None, max_length=255, description="位置")
    work_center_code: Optional[str] = Field(None, max_length=100, description="所属工作中心")
    status: str = Field(default="idle", max_length=20, description="状态：idle/running/maintenance/fault/down")
    purchase_date: Optional[datetime] = Field(None, description="购入日期")
    warranty_date: Optional[datetime] = Field(None, description="保修到期日期")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = Field(default=True, description="是否启用")


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    equipment_code: Optional[str] = Field(None, min_length=1, max_length=100, description="设备编码")
    equipment_name: Optional[str] = Field(None, min_length=1, max_length=255, description="设备名称")
    equipment_type: Optional[str] = Field(None, max_length=50, description="设备类型")
    model: Optional[str] = Field(None, max_length=100, description="设备型号")
    manufacturer: Optional[str] = Field(None, max_length=255, description="制造商")
    location: Optional[str] = Field(None, max_length=255, description="位置")
    work_center_code: Optional[str] = Field(None, max_length=100, description="所属工作中心")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    purchase_date: Optional[datetime] = Field(None, description="购入日期")
    warranty_date: Optional[datetime] = Field(None, description="保修到期日期")
    description: Optional[str] = Field(None, description="描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class EquipmentResponse(EquipmentBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EquipmentListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    equipment_code: Optional[str] = Field(None, description="设备编码")
    equipment_name: Optional[str] = Field(None, description="设备名称")
    equipment_type: Optional[str] = Field(None, description="设备类型")
    status: Optional[str] = Field(None, description="状态")


T = TypeVar("T")

class ListResponse(BaseModel, Generic[T]):
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[T] = Field(..., description="数据列表")


class StartWORequest(BaseModel):
    operator: str = Field(..., max_length=100, description="操作员")
    equipment_code: Optional[str] = Field(None, max_length=100, description="设备编码")
    shift_code: Optional[str] = Field(None, max_length=100, description="班次编码")


class SuspendWORequest(BaseModel):
    suspend_reason: str = Field(..., max_length=50, description="暂停原因：equipment/quality/exception")
    suspend_source: Optional[str] = Field(None, max_length=100, description="暂停来源编码")


class ResumeWORequest(BaseModel):
    operator: Optional[str] = Field(None, max_length=100, description="确认恢复的操作员")