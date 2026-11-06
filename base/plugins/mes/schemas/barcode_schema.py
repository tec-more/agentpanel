from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class BarcodeParseRequest(BaseModel):
    barcode: str = Field(..., max_length=100, description="条码值")


class BarcodeParseResponse(BaseModel):
    barcode: str
    barcode_type: str
    reference_code: str
    is_active: bool

    class Config:
        from_attributes = True


class BarcodeGenerateRequest(BaseModel):
    barcode_type: str = Field(..., max_length=20, description="条码类型：work_order/material/process")
    reference_code: str = Field(..., max_length=100, description="关联业务编码")


class BarcodeGenerateResponse(BaseModel):
    barcode: str
    barcode_type: str
    reference_code: str