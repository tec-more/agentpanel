from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from decimal import Decimal


class EnergyRecordCreate(BaseModel):
    equipment_code: str = Field(..., max_length=100, description="设备编码")
    energy_type: str = Field(..., max_length=20, description="能耗类型：electric/water/gas")
    consumption_value: Decimal = Field(..., gt=0, description="消耗值")
    unit: str = Field(..., max_length=20, description="计量单位(kWh/m³)")
    record_time: datetime = Field(..., description="记录时间")
    work_center_code: str = Field(..., max_length=100, description="工作中心编码")
    shift_code: Optional[str] = Field(None, max_length=100, description="班次编码")


class EnergyRecordResponse(BaseModel):
    id: int
    equipment_code: str
    energy_type: str
    consumption_value: float
    unit: str
    record_time: Optional[datetime] = None
    work_center_code: str
    shift_code: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnergyStatisticsQuery(BaseModel):
    work_center_code: Optional[str] = Field(None, description="工作中心编码")
    energy_type: Optional[str] = Field(None, description="能耗类型")
    start_date: Optional[str] = Field(None, description="开始日期")
    end_date: Optional[str] = Field(None, description="结束日期")


class EnergyStatisticsResponse(BaseModel):
    total_consumption: float = 0
    unit_product_consumption: float = 0
    records: list = []