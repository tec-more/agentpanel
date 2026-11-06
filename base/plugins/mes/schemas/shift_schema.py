from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class ShiftDefinitionCreate(BaseModel):
    shift_code: str = Field(..., max_length=20, description="班次编码")
    shift_name: str = Field(..., max_length=50, description="班次名称")
    start_time: str = Field(..., max_length=5, description="班次开始时间(HH:MM)")
    end_time: str = Field(..., max_length=5, description="班次结束时间(HH:MM)")
    work_center_code: Optional[str] = Field(None, max_length=100, description="关联工作中心编码")
    description: Optional[str] = Field(None, description="描述")


class ShiftDefinitionResponse(BaseModel):
    id: int
    shift_code: str
    shift_name: str
    start_time: str
    end_time: str
    work_center_code: Optional[str] = None
    is_active: bool = True
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShiftScheduleCreate(BaseModel):
    shift_code: str = Field(..., max_length=20, description="班次编码")
    work_center_code: str = Field(..., max_length=100, description="工作中心编码")
    schedule_date: str = Field(..., description="排班日期(YYYY-MM-DD)")
    operator_list: List[str] = Field(..., description="排班人员列表")
    leader: str = Field(..., max_length=100, description="班组长")


class ShiftScheduleResponse(BaseModel):
    id: int
    shift_code: str
    work_center_code: str
    date: Optional[str] = None
    operator_list: list = []
    leader: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShiftHandoverCreate(BaseModel):
    shift_code: str = Field(..., max_length=20, description="班次编码")
    work_center_code: str = Field(..., max_length=100, description="工作中心编码")
    handover_date: str = Field(..., description="交接班日期(YYYY-MM-DD)")
    outgoing_leader: str = Field(..., max_length=100, description="交班班组长")
    incoming_leader: str = Field(..., max_length=100, description="接班班组长")
    equipment_status: str = Field(..., description="设备状态描述")
    production_progress: str = Field(..., description="生产进度描述")
    exception_items: str = Field(..., description="异常事项")
    remark: Optional[str] = Field(None, description="备注")


class ShiftHandoverResponse(BaseModel):
    id: int
    shift_code: str
    work_center_code: str
    date: Optional[str] = None
    outgoing_leader: str
    incoming_leader: str
    equipment_status: str
    production_progress: str
    exception_items: str
    remark: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShiftListQuery(BaseModel):
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=200, description="每页数量")
    shift_code: Optional[str] = Field(None, description="班次编码")
    work_center_code: Optional[str] = Field(None, description="工作中心编码")