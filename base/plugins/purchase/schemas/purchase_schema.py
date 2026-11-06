from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal


class SupplierCreate(BaseModel):
    supplier_code: Optional[str] = None
    supplier_name: str
    supplier_type: Optional[str] = "distributor"
    status: Optional[str] = "active"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    tax_id: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    credit_limit: Optional[Decimal] = 0
    payment_term: Optional[str] = None
    delivery_days: Optional[int] = None
    remark: Optional[str] = None
    is_preferred: Optional[bool] = False


class SupplierUpdate(BaseModel):
    supplier_name: Optional[str] = None
    supplier_type: Optional[str] = None
    status: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    tax_id: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    payment_term: Optional[str] = None
    delivery_days: Optional[int] = None
    remark: Optional[str] = None
    is_preferred: Optional[bool] = None


class SupplierResponse(BaseModel):
    id: int
    supplier_code: str
    supplier_name: str
    supplier_type: str
    supplier_type_label: str
    status: str
    status_label: str
    contact_name: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    address: Optional[str]
    province: Optional[str]
    city: Optional[str]
    district: Optional[str]
    tax_id: Optional[str]
    bank_name: Optional[str]
    bank_account: Optional[str]
    credit_limit: float
    payment_term: Optional[str]
    delivery_days: Optional[int]
    remark: Optional[str]
    is_preferred: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class PurchaseOrderItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: str
    product_spec: Optional[str] = None
    product_unit: Optional[str] = "件"
    quantity: int = 1
    unit_price: Decimal = 0
    tax_rate: Optional[Decimal] = 0
    remark: Optional[str] = None


class PurchaseOrderItemUpdate(BaseModel):
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    product_spec: Optional[str] = None
    product_unit: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    remark: Optional[str] = None


class PurchaseOrderItemResponse(BaseModel):
    id: int
    purchase_order_id: int
    product_id: Optional[int]
    product_code: Optional[str]
    product_name: str
    product_spec: Optional[str]
    product_unit: str
    quantity: int
    received_quantity: int
    unit_price: float
    total_price: float
    tax_rate: float
    tax_amount: float
    remark: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    order_date: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    warehouse_id: Optional[int] = None
    warehouse_code: Optional[str] = None
    currency: Optional[str] = "CNY"
    exchange_rate: Optional[Decimal] = 1
    remark: Optional[str] = None
    created_by: Optional[str] = None
    items: List[PurchaseOrderItemCreate] = []


class PurchaseOrderUpdate(BaseModel):
    supplier_id: Optional[int] = None
    order_date: Optional[str] = None
    expected_delivery_date: Optional[str] = None
    warehouse_id: Optional[int] = None
    warehouse_code: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    remark: Optional[str] = None
    items: Optional[List[PurchaseOrderItemUpdate]] = None


class PurchaseOrderResponse(BaseModel):
    id: int
    order_no: str
    supplier_id: int
    supplier_code: Optional[str]
    supplier_name: Optional[str]
    status: str
    status_label: str
    status_color: str
    order_date: Optional[str]
    expected_delivery_date: Optional[str]
    actual_delivery_date: Optional[str]
    total_amount: float
    paid_amount: float
    currency: str
    exchange_rate: float
    warehouse_id: Optional[int]
    warehouse_code: Optional[str]
    remark: Optional[str]
    created_by: Optional[str]
    total_quantity: int
    received_quantity: int
    items: List[PurchaseOrderItemResponse]
    created_at: Optional[str]
    updated_at: Optional[str]


class PurchaseReceiptItemCreate(BaseModel):
    order_item_id: Optional[int] = None
    product_id: Optional[int] = None
    product_code: Optional[str] = None
    product_name: str
    product_spec: Optional[str] = None
    product_unit: Optional[str] = "件"
    quantity: int = 1
    unit_price: Decimal = 0
    batch_no: Optional[str] = None
    expire_date: Optional[str] = None
    remark: Optional[str] = None


class PurchaseReceiptItemResponse(BaseModel):
    id: int
    receipt_id: int
    order_item_id: Optional[int]
    product_id: Optional[int]
    product_code: Optional[str]
    product_name: str
    product_spec: Optional[str]
    product_unit: str
    quantity: int
    unit_price: float
    total_price: float
    batch_no: Optional[str]
    expire_date: Optional[str]
    remark: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class PurchaseReceiptCreate(BaseModel):
    purchase_order_id: int
    receipt_date: Optional[str] = None
    warehouse_id: Optional[int] = None
    warehouse_code: Optional[str] = None
    location_id: Optional[int] = None
    location_code: Optional[str] = None
    inspector: Optional[str] = None
    is_qualified: Optional[bool] = True
    quality_result: Optional[str] = None
    remark: Optional[str] = None
    created_by: Optional[str] = None
    items: List[PurchaseReceiptItemCreate] = []


class PurchaseReceiptUpdate(BaseModel):
    receipt_date: Optional[str] = None
    warehouse_id: Optional[int] = None
    warehouse_code: Optional[str] = None
    location_id: Optional[int] = None
    location_code: Optional[str] = None
    inspector: Optional[str] = None
    is_qualified: Optional[bool] = None
    quality_result: Optional[str] = None
    remark: Optional[str] = None
    items: Optional[List[PurchaseReceiptItemCreate]] = None


class PurchaseReceiptResponse(BaseModel):
    id: int
    receipt_no: str
    purchase_order_id: int
    purchase_order_no: Optional[str]
    supplier_id: Optional[int]
    supplier_name: Optional[str]
    receipt_date: Optional[str]
    warehouse_id: Optional[int]
    warehouse_code: Optional[str]
    location_id: Optional[int]
    location_code: Optional[str]
    total_amount: float
    inspector: Optional[str]
    is_qualified: bool
    quality_result: Optional[str]
    remark: Optional[str]
    created_by: Optional[str]
    items: List[PurchaseReceiptItemResponse]
    created_at: Optional[str]
    updated_at: Optional[str]