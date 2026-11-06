from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date


class SubcontractingOrderCreate(BaseModel):
    product_code: str
    product_name: str
    plan_quantity: Decimal
    supplier_code: str
    supplier_name: str
    process_code: Optional[str] = None
    process_name: Optional[str] = None
    processing_unit_price: Optional[Decimal] = 0
    scrap_rate: Optional[Decimal] = 0
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    source_planned_order_code: Optional[str] = None
    source_mps_code: Optional[str] = None
    remark: Optional[str] = None


class SubcontractingOrderUpdate(BaseModel):
    product_name: Optional[str] = None
    plan_quantity: Optional[Decimal] = None
    supplier_name: Optional[str] = None
    process_name: Optional[str] = None
    processing_unit_price: Optional[Decimal] = None
    scrap_rate: Optional[Decimal] = None
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    remark: Optional[str] = None


class SubcontractingOrderResponse(BaseModel):
    id: int
    sc_code: str
    product_code: str
    product_name: str
    plan_quantity: Decimal
    actual_quantity: Decimal = 0
    supplier_code: str
    supplier_name: str
    process_code: Optional[str] = None
    process_name: Optional[str] = None
    processing_unit_price: Decimal = 0
    scrap_rate: Decimal = 0
    status: str
    status_label: str = ""
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    actual_start_date: Optional[str] = None
    actual_end_date: Optional[str] = None
    source_planned_order_code: Optional[str] = None
    source_mps_code: Optional[str] = None
    total_issued_quantity: Decimal = 0
    total_received_quantity: Decimal = 0
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SubcontractingOrderListQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1)
    status: Optional[str] = None
    supplier_code: Optional[str] = None
    product_code: Optional[str] = None


class SubcontractingIssueLineCreate(BaseModel):
    material_code: str
    material_name: str
    required_quantity: Decimal
    actual_quantity: Decimal = 0
    uom: str
    bom_quantity: Optional[Decimal] = 0
    is_bom_material: bool = True


class SubcontractingIssueCreate(BaseModel):
    sc_code: str
    issue_type: str = "auto"
    source_warehouse_code: str
    source_location_code: Optional[str] = None
    supplier_location_code: Optional[str] = None
    applicant: Optional[str] = None
    remark: Optional[str] = None
    lines: List[SubcontractingIssueLineCreate] = []


class SubcontractingIssueLineResponse(BaseModel):
    id: int
    issue_id: int
    material_code: str
    material_name: str
    required_quantity: Decimal
    actual_quantity: Decimal
    uom: str
    bom_quantity: Decimal
    is_bom_material: bool


class SubcontractingIssueResponse(BaseModel):
    id: int
    issue_code: str
    sc_code: str
    issue_type: str
    source_warehouse_code: str
    source_location_code: Optional[str] = None
    supplier_location_code: Optional[str] = None
    status: str
    status_label: str = ""
    applicant: Optional[str] = None
    confirmer: Optional[str] = None
    confirmed_at: Optional[str] = None
    remark: Optional[str] = None
    lines: List[SubcontractingIssueLineResponse] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SubcontractingIssueListQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1)
    sc_code: Optional[str] = None
    status: Optional[str] = None


class SubcontractingReceiptLineCreate(BaseModel):
    product_code: str
    product_name: str
    receipt_quantity: Decimal
    qualified_quantity: Decimal = 0
    unqualified_quantity: Decimal = 0
    concession_quantity: Optional[Decimal] = 0
    uom: str
    batch_no: Optional[str] = None


class SubcontractingReceiptCreate(BaseModel):
    sc_code: str
    supplier_code: str
    receipt_warehouse_code: str
    receipt_location_code: Optional[str] = None
    inspection_result: Optional[str] = None
    inspector: Optional[str] = None
    receiver: Optional[str] = None
    remark: Optional[str] = None
    lines: List[SubcontractingReceiptLineCreate] = []


class SubcontractingReceiptLineResponse(BaseModel):
    id: int
    receipt_id: int
    product_code: str
    product_name: str
    receipt_quantity: Decimal
    qualified_quantity: Decimal
    unqualified_quantity: Decimal
    concession_quantity: Decimal
    uom: str
    batch_no: Optional[str] = None


class SubcontractingReceiptResponse(BaseModel):
    id: int
    receipt_code: str
    sc_code: str
    supplier_code: str
    receipt_warehouse_code: str
    receipt_location_code: Optional[str] = None
    inspection_result: Optional[str] = None
    inspector: Optional[str] = None
    status: str
    status_label: str = ""
    receiver: Optional[str] = None
    confirmed_at: Optional[str] = None
    remark: Optional[str] = None
    lines: List[SubcontractingReceiptLineResponse] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SubcontractingReceiptListQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1)
    sc_code: Optional[str] = None
    status: Optional[str] = None


class SubcontractingSettlementCreate(BaseModel):
    sc_code: str
    supplier_code: str
    period_start_date: Optional[str] = None
    period_end_date: Optional[str] = None
    processing_unit_price: Optional[Decimal] = 0
    concession_discount_rate: Optional[Decimal] = 1
    currency: Optional[str] = "CNY"
    remark: Optional[str] = None


class SubcontractingSettlementResponse(BaseModel):
    id: int
    settlement_code: str
    sc_code: str
    supplier_code: str
    period_start_date: Optional[str] = None
    period_end_date: Optional[str] = None
    qualified_quantity: Decimal = 0
    concession_quantity: Decimal = 0
    processing_unit_price: Decimal = 0
    concession_discount_rate: Decimal = 1
    settlement_amount: Decimal = 0
    currency: str = "CNY"
    status: str
    status_label: str = ""
    submitter: Optional[str] = None
    approver: Optional[str] = None
    confirmer: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SubcontractingSettlementListQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1)
    sc_code: Optional[str] = None
    supplier_code: Optional[str] = None
    status: Optional[str] = None


class SubcontractingTransitResponse(BaseModel):
    material_code: str
    material_name: str = ""
    supplier_code: str
    supplier_name: str = ""
    transit_quantity: Decimal = 0
    uom: str = ""


class SubcontractingTransitListQuery(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1)
    material_code: Optional[str] = None
    supplier_code: Optional[str] = None


class ListResponse(BaseModel):
    items: list = []
    total: int = 0