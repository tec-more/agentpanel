from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field


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


class EquipmentMaintenanceBase(BaseModel):
    maintenance_code: str = Field(..., min_length=1, max_length=100, description="保养单号")
    equipment_code: str = Field(..., min_length=1, max_length=100, description="设备编码")
    equipment_name: str = Field(..., min_length=1, max_length=255, description="设备名称")
    maintenance_type: str = Field(..., max_length=20, description="保养类型：daily/weekly/monthly/quarterly/yearly")
    planned_date: Optional[datetime] = Field(None, description="计划保养日期")
    status: str = Field(default="pending", max_length=20, description="状态：pending/completed")
    operator: Optional[str] = Field(None, max_length=100, description="操作员")
    items: Optional[List[Dict[str, Any]]] = Field(None, description="保养项目")
    remark: Optional[str] = Field(None, description="备注")


class EquipmentMaintenanceCreate(EquipmentMaintenanceBase):
    pass


class EquipmentMaintenanceUpdate(BaseModel):
    actual_date: Optional[datetime] = Field(None, description="实际保养日期")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    operator: Optional[str] = Field(None, max_length=100, description="操作员")
    items: Optional[List[Dict[str, Any]]] = Field(None, description="保养项目")
    remark: Optional[str] = Field(None, description="备注")


class EquipmentMaintenanceResponse(EquipmentMaintenanceBase):
    id: int
    actual_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EquipmentMaintenanceListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    maintenance_code: Optional[str] = Field(None, description="保养单号")
    equipment_code: Optional[str] = Field(None, description="设备编码")
    maintenance_type: Optional[str] = Field(None, description="保养类型")
    status: Optional[str] = Field(None, description="状态")


class EquipmentFaultBase(BaseModel):
    fault_code: str = Field(..., min_length=1, max_length=100, description="故障单号")
    equipment_code: str = Field(..., min_length=1, max_length=100, description="设备编码")
    equipment_name: str = Field(..., min_length=1, max_length=255, description="设备名称")
    fault_type: str = Field(..., max_length=50, description="故障类型")
    fault_level: str = Field(default="minor", max_length=20, description="故障级别：minor/major/critical")
    fault_time: Optional[datetime] = Field(None, description="故障发生时间")
    status: str = Field(default="open", max_length=20, description="状态：open/processing/resolved/closed")
    description: Optional[str] = Field(None, description="故障描述")
    operator: Optional[str] = Field(None, max_length=100, description="处理人")


class EquipmentFaultCreate(EquipmentFaultBase):
    pass


class EquipmentFaultUpdate(BaseModel):
    recovery_time: Optional[datetime] = Field(None, description="恢复时间")
    status: Optional[str] = Field(None, max_length=20, description="状态")
    solution: Optional[str] = Field(None, description="解决方案")
    operator: Optional[str] = Field(None, max_length=100, description="处理人")


class EquipmentFaultResponse(EquipmentFaultBase):
    id: int
    recovery_time: Optional[datetime] = None
    solution: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EquipmentFaultListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    fault_code: Optional[str] = Field(None, description="故障单号")
    equipment_code: Optional[str] = Field(None, description="设备编码")
    fault_level: Optional[str] = Field(None, description="故障级别")
    status: Optional[str] = Field(None, description="状态")


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[T] = Field(..., description="数据列表")