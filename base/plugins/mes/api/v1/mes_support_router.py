from typing import Optional
from fastapi import APIRouter, HTTPException

from base.plugins.mes.services.mes_support_service import (
    TraceService, DashboardService, BarcodeService,
    ShiftService, ExceptionService, ToolingService, EnergyService
)
from base.plugins.mes.schemas.trace_schema import TraceForwardQuery, TraceBackwardQuery
from base.plugins.mes.schemas.barcode_schema import BarcodeParseRequest, BarcodeGenerateRequest
from base.plugins.mes.schemas.shift_schema import (
    ShiftDefinitionCreate, ShiftScheduleCreate, ShiftHandoverCreate
)
from base.plugins.mes.schemas.exception_schema import ProductionExceptionCreate, ProductionExceptionHandle
from base.plugins.mes.schemas.tooling_schema import ToolingCreate, ToolingValidateRequest
from base.plugins.mes.schemas.energy_schema import EnergyRecordCreate, EnergyStatisticsQuery
from base.common.response import success_response

trace_router = APIRouter(prefix="/trace", tags=["生产追溯"])

@trace_router.get("/forward", summary="正向追溯")
async def forward_trace(material_batch_no: str):
    records = await TraceService.forward_trace(material_batch_no)
    return success_response(data=records)

@trace_router.get("/backward", summary="反向追溯")
async def backward_trace(product_batch_no: str):
    records = await TraceService.backward_trace(product_batch_no)
    return success_response(data=records)


dashboard_router = APIRouter(prefix="/dashboard", tags=["生产看板"])

@dashboard_router.get("/oee", summary="OEE查询")
async def get_oee(work_center_code: Optional[str] = None, period: str = "day"):
    data = await DashboardService.get_oee(work_center_code, period)
    return success_response(data=data)

@dashboard_router.get("/production", summary="产量统计")
async def get_production_stats(work_center_code: Optional[str] = None, period: str = "day"):
    data = await DashboardService.get_production_stats(work_center_code, period)
    return success_response(data=data)

@dashboard_router.get("/progress", summary="实时进度")
async def get_progress():
    data = await DashboardService.get_progress()
    return success_response(data=data)


barcode_router = APIRouter(prefix="/barcode", tags=["条码管理"])

@barcode_router.post("/generate", summary="生成条码")
async def generate_barcode(data: BarcodeGenerateRequest):
    try:
        record = await BarcodeService.generate_barcode(data)
        return success_response(data=record, msg="条码生成成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@barcode_router.post("/parse", summary="解析条码")
async def parse_barcode(data: BarcodeParseRequest):
    try:
        record = await BarcodeService.parse_barcode(data.barcode)
        return success_response(data=record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


shift_router = APIRouter(prefix="/shift", tags=["班次管理"])

@shift_router.post("/definition", summary="创建班次定义")
async def create_shift(data: ShiftDefinitionCreate):
    try:
        shift = await ShiftService.create_shift(data)
        return success_response(data=shift, msg="班次创建成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@shift_router.get("/definition", summary="获取班次列表")
async def list_shifts(work_center_code: Optional[str] = None):
    shifts = await ShiftService.get_shifts(work_center_code)
    return success_response(data=shifts)

@shift_router.post("/schedule", summary="创建排班")
async def create_schedule(data: ShiftScheduleCreate):
    schedule = await ShiftService.create_schedule(data)
    return success_response(data=schedule, msg="排班创建成功")

@shift_router.post("/handover", summary="创建交接班记录")
async def create_handover(data: ShiftHandoverCreate):
    handover = await ShiftService.create_handover(data)
    return success_response(data=handover, msg="交接班记录创建成功")


exception_router = APIRouter(prefix="/exception", tags=["生产异常"])

@exception_router.post("", summary="上报异常")
async def report_exception(data: ProductionExceptionCreate):
    try:
        exc = await ExceptionService.report_exception(data)
        return success_response(data=exc, msg="异常上报成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@exception_router.post("/{exception_id}/handle", summary="处理异常")
async def handle_exception(exception_id: int, data: ProductionExceptionHandle):
    try:
        exc = await ExceptionService.handle_exception(exception_id, data)
        if not exc:
            raise HTTPException(status_code=404, detail="异常不存在")
        return success_response(data=exc, msg="异常处理成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@exception_router.get("", summary="获取异常列表")
async def list_exceptions(
    page: int = 1, page_size: int = 10,
    exception_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    work_center_code: Optional[str] = None
):
    items, total = await ExceptionService.get_list(
        page=page, page_size=page_size,
        exception_type=exception_type, severity=severity,
        status=status, work_center_code=work_center_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


tooling_router = APIRouter(prefix="/tooling", tags=["工装夹具"])

@tooling_router.post("", summary="创建工装")
async def create_tooling(data: ToolingCreate):
    try:
        tooling = await ToolingService.create_tooling(data)
        return success_response(data=tooling, msg="工装创建成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@tooling_router.post("/{tooling_id}/validate", summary="校验工装")
async def validate_tooling(tooling_id: int):
    tooling = await Tooling.filter(id=tooling_id).first()
    if not tooling:
        raise HTTPException(status_code=404, detail="工装不存在")
    result = await ToolingService.validate_tooling(tooling.tooling_code)
    return success_response(data=result)

@tooling_router.get("", summary="获取工装列表")
async def list_toolings(
    page: int = 1, page_size: int = 10,
    tooling_code: Optional[str] = None,
    tooling_type: Optional[str] = None,
    status: Optional[str] = None,
    work_center_code: Optional[str] = None
):
    items, total = await ToolingService.get_list(
        page=page, page_size=page_size,
        tooling_code=tooling_code, tooling_type=tooling_type,
        status=status, work_center_code=work_center_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


energy_router = APIRouter(prefix="/energy", tags=["能耗管理"])

@energy_router.post("/record", summary="录入能耗数据")
async def record_energy(data: EnergyRecordCreate):
    record = await EnergyService.record_energy(data)
    return success_response(data=record, msg="能耗数据录入成功")

@energy_router.get("/statistics", summary="能耗统计查询")
async def get_statistics(
    work_center_code: Optional[str] = None,
    energy_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    data = await EnergyService.get_statistics(work_center_code, energy_type, start_date, end_date)
    return success_response(data=data)

mes_support_router = APIRouter()
mes_support_router.include_router(trace_router)
mes_support_router.include_router(dashboard_router)
mes_support_router.include_router(barcode_router)
mes_support_router.include_router(shift_router)
mes_support_router.include_router(exception_router)
mes_support_router.include_router(tooling_router)
mes_support_router.include_router(energy_router)