from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from decimal import Decimal


class MaterialRequisitionDetailBase(BaseModel):
    material_code: str = Field(..., max_length=100, description="物料编码")
    material_name: str = Field(..., max_length=255, description="物料名称")
    required_quantity: Decimal = Field(..., gt=0, description="需求数量")
    unit: str = Field(..., max_length=20, description="计量单位")
    process_code: Optional[str] = Field(None, max_length=100, description="关联工序编码")
    substitute_material_code: Optional[str] = Field(None, max_length=100, description="替代物料编码")


class MaterialRequisitionCreate(BaseModel):
    mo_code: str = Field(..., max_length=100, description="制造单编码")
    requisition_type: str = Field(default="auto", max_length=20, description="领料类型：auto/manual/by_process")
    warehouse_code: str = Field(..., max_length=100, description="领料仓库编码")
    location_code: str = Field(..., max_length=100, description="领料库位编码")
    applicant: str = Field(..., max_length=100, description="申请人")
    remark: Optional[str] = Field(None, description="备注")
    details: List[MaterialRequisitionDetailBase] = Field(default_factory=list, description="领料明细")


class MaterialRequisitionResponse(BaseModel):
    id: int
    requisition_code: str
    mo_code: str
    requisition_type: str
    status: str
    warehouse_code: str
    location_code: str
    applicant: str
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaterialReturnCreate(BaseModel):
    mo_code: str = Field(..., max_length=100, description="制造单编码")
    requisition_code: str = Field(..., max_length=100, description="关联领料单号")
    warehouse_code: str = Field(..., max_length=100, description="退料仓库编码")
    location_code: str = Field(..., max_length=100, description="退料库位编码")
    operator: str = Field(..., max_length=100, description="操作员")
    remark: Optional[str] = Field(None, description="备注")


class MaterialReturnResponse(BaseModel):
    id: int
    return_code: str
    mo_code: str
    requisition_code: str
    status: str
    warehouse_code: str
    location_code: str
    operator: str
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductionReceiptCreate(BaseModel):
    mo_code: str = Field(..., max_length=100, description="制造单编码")
    product_code: str = Field(..., max_length=100, description="产品编码")
    product_name: str = Field(..., max_length=255, description="产品名称")
    quantity: int = Field(..., ge=1, description="入库数量")
    unit: str = Field(..., max_length=20, description="计量单位")
    warehouse_code: str = Field(..., max_length=100, description="入库仓库编码")
    location_code: str = Field(..., max_length=100, description="入库库位编码")
    inspection_result: str = Field(..., max_length=20, description="检验结果：qualified/concession")
    remark: Optional[str] = Field(None, description="备注")


class ProductionReceiptResponse(BaseModel):
    id: int
    receipt_code: str
    mo_code: str
    product_code: str
    product_name: str
    batch_no: str
    quantity: int
    unit: str
    warehouse_code: str
    location_code: str
    inspection_result: str
    status: str
    remark: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaterialRequisitionListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mo_code: Optional[str] = Field(None, description="制造单编码")
    status: Optional[str] = Field(None, description="状态")
    requisition_type: Optional[str] = Field(None, description="领料类型")


class MaterialReturnListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mo_code: Optional[str] = Field(None, description="制造单编码")
    status: Optional[str] = Field(None, description="状态")


class ProductionReceiptListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    mo_code: Optional[str] = Field(None, description="制造单编码")
    status: Optional[str] = Field(None, description="状态")