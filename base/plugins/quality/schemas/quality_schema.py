from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field


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


class InspectionStandardBase(BaseModel):
    standard_code: str = Field(..., min_length=1, max_length=100, description="标准编码")
    standard_name: str = Field(..., min_length=1, max_length=255, description="标准名称")
    material_code: Optional[str] = Field(None, max_length=100, description="适用物料编码")
    inspection_type: str = Field(..., max_length=20, description="检验类型：IQC/IPQC/FQC/OQC")
    items: Optional[List[Dict[str, Any]]] = Field(None, description="检验项目列表")
    sampling_rule: Optional[str] = Field(None, description="抽样规则")
    is_active: bool = Field(default=True, description="是否启用")


class InspectionStandardCreate(InspectionStandardBase):
    pass


class InspectionStandardUpdate(BaseModel):
    standard_name: Optional[str] = Field(None, min_length=1, max_length=255, description="标准名称")
    material_code: Optional[str] = Field(None, max_length=100, description="适用物料编码")
    inspection_type: Optional[str] = Field(None, max_length=20, description="检验类型")
    items: Optional[List[Dict[str, Any]]] = Field(None, description="检验项目列表")
    sampling_rule: Optional[str] = Field(None, description="抽样规则")
    is_active: Optional[bool] = Field(None, description="是否启用")


class InspectionStandardResponse(InspectionStandardBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InspectionStandardListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    standard_code: Optional[str] = Field(None, description="标准编码")
    standard_name: Optional[str] = Field(None, description="标准名称")
    inspection_type: Optional[str] = Field(None, description="检验类型")
    is_active: Optional[bool] = Field(None, description="是否启用")


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页")
    page_size: int = Field(..., description="每页数量")
    items: List[T] = Field(..., description="数据列表")