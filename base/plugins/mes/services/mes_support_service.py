from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
try:
    from base.plugins.mes.models.trace import TraceRecord
    from base.plugins.mes.models.barcode import BarcodeRecord
    from base.plugins.mes.models.shift import ShiftDefinition, ShiftSchedule, ShiftHandover
    from base.plugins.mes.models.exception import ProductionException
    from base.plugins.mes.models.tooling import Tooling, ToolingProcessBinding
    from base.plugins.mes.models.energy import EnergyRecord
    from base.plugins.mes.models.production import WorkOrder
    from base.plugins.mes.schemas.trace_schema import TraceForwardQuery, TraceBackwardQuery
    from base.plugins.mes.schemas.barcode_schema import BarcodeGenerateRequest
    from base.plugins.mes.schemas.shift_schema import (
        ShiftDefinitionCreate, ShiftScheduleCreate, ShiftHandoverCreate
    )
    from base.plugins.mes.schemas.exception_schema import ProductionExceptionCreate, ProductionExceptionHandle
    from base.plugins.mes.schemas.tooling_schema import ToolingCreate, ToolingValidateRequest
    from base.plugins.mes.schemas.energy_schema import EnergyRecordCreate
except ImportError:
    TraceRecord = None
    BarcodeRecord = None
    ShiftDefinition = None
    ShiftSchedule = None
    ShiftHandover = None
    ProductionException = None
    Tooling = None
    ToolingProcessBinding = None
    EnergyRecord = None
    WorkOrder = None


class TraceService:
    model = "trace"
    @staticmethod
    async def forward_trace(material_batch_no: str) -> List[TraceRecord]:
        return await TraceRecord.filter(material_batch_no=material_batch_no).order_by('created_at')

    @staticmethod
    async def backward_trace(product_batch_no: str) -> List[TraceRecord]:
        return await TraceRecord.filter(product_batch_no=product_batch_no).order_by('created_at')


class DashboardService:
    model = "dashboard"
    @staticmethod
    async def get_oee(work_center_code: str = None, period: str = "day") -> Dict[str, Any]:
        return {
            "availability_rate": 0.0,
            "performance_rate": 0.0,
            "quality_rate": 0.0,
            "oee": 0.0,
            "work_center_code": work_center_code,
            "period": period
        }

    @staticmethod
    async def get_production_stats(work_center_code: str = None, period: str = "day") -> Dict[str, Any]:
        return {
            "planned_quantity": 0,
            "actual_quantity": 0,
            "completion_rate": 0.0,
            "work_center_code": work_center_code,
            "period": period
        }

    @staticmethod
    async def get_progress() -> List[Dict[str, Any]]:
        if WorkOrder is None:
            return []
        work_orders = await WorkOrder.filter(status__in=["processing", "suspended"]).limit(50)
        result = []
        for wo in work_orders:
            completion = (wo.actual_quantity / wo.quantity * 100) if wo.quantity > 0 else 0
            result.append({
                "wo_code": wo.wo_code,
                "mo_code": wo.mo_code,
                "product_code": wo.product_code,
                "status": wo.status,
                "planned_quantity": wo.quantity,
                "actual_quantity": wo.actual_quantity,
                "completion_rate": round(completion, 2)
            })
        return result


class BarcodeService:
    model = "barcode"
    @staticmethod
    async def generate_barcode(data: BarcodeGenerateRequest) -> BarcodeRecord:
        if data.barcode_type == "work_order":
            barcode_value = f"WO-{data.reference_code}"
        elif data.barcode_type == "material":
            barcode_value = f"MAT-{data.reference_code}"
        elif data.barcode_type == "process":
            barcode_value = f"PROC-{data.reference_code}"
        else:
            barcode_value = f"BC-{data.reference_code}"

        existing = await BarcodeRecord.filter(barcode=barcode_value).first()
        if existing:
            return existing

        return await BarcodeRecord.create(
            barcode=barcode_value,
            barcode_type=data.barcode_type,
            reference_code=data.reference_code
        )

    @staticmethod
    async def parse_barcode(barcode: str) -> Optional[BarcodeRecord]:
        record = await BarcodeRecord.filter(barcode=barcode).first()
        if not record:
            raise ValueError("条码不存在")
        if not record.is_active:
            raise ValueError("条码已失效")
        return record


class ShiftService:
    model = "shift"
    @staticmethod
    async def create_shift(data: ShiftDefinitionCreate) -> ShiftDefinition:
        existing = await ShiftDefinition.filter(
            work_center_code=data.work_center_code,
            is_active=True
        )
        for s in existing:
            if s.shift_code != data.shift_code:
                if (data.start_time < s.end_time and data.end_time > s.start_time):
                    raise ValueError(f"班次时间与{s.shift_name}冲突")

        return await ShiftDefinition.create(
            shift_code=data.shift_code,
            shift_name=data.shift_name,
            start_time=data.start_time,
            end_time=data.end_time,
            work_center_code=data.work_center_code,
            description=data.description
        )

    @staticmethod
    async def create_schedule(data: ShiftScheduleCreate) -> ShiftSchedule:
        return await ShiftSchedule.create(
            shift_code=data.shift_code,
            work_center_code=data.work_center_code,
            date=data.schedule_date,
            operator_list=data.operator_list,
            leader=data.leader
        )

    @staticmethod
    async def create_handover(data: ShiftHandoverCreate) -> ShiftHandover:
        return await ShiftHandover.create(
            shift_code=data.shift_code,
            work_center_code=data.work_center_code,
            date=data.handover_date,
            outgoing_leader=data.outgoing_leader,
            incoming_leader=data.incoming_leader,
            equipment_status=data.equipment_status,
            production_progress=data.production_progress,
            exception_items=data.exception_items,
            remark=data.remark
        )

    @staticmethod
    async def get_shifts(work_center_code: str = None) -> List[ShiftDefinition]:
        query = ShiftDefinition.filter(is_active=True)
        if work_center_code:
            query = query.filter(work_center_code=work_center_code)
        return await query.order_by('start_time')


class ExceptionService:
    model = "exception"
    @staticmethod
    async def report_exception(data: ProductionExceptionCreate) -> ProductionException:
        import random
        exception_code = f"EXC{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100,999)}"
        exception = await ProductionException.create(
            exception_code=exception_code,
            exception_type=data.exception_type,
            severity=data.severity,
            wo_code=data.wo_code,
            mo_code=data.mo_code,
            work_center_code=data.work_center_code,
            description=data.description,
            reporter=data.reporter
        )

        if data.wo_code and WorkOrder is not None:
            wo = await WorkOrder.filter(wo_code=data.wo_code).first()
            if wo and wo.status == "processing":
                wo.status = "suspended"
                wo.suspend_reason = "exception"
                wo.suspend_source = exception_code
                wo.suspended_at = datetime.now()
                await wo.save()

        return exception

    @staticmethod
    async def handle_exception(exception_id: int, data: ProductionExceptionHandle) -> Optional[ProductionException]:
        exc = await ProductionException.filter(id=exception_id).first()
        if not exc:
            return None
        if exc.status not in ("reported", "processing"):
            raise ValueError("只能处理未解决的异常")

        exc.status = "resolved"
        exc.handler = data.handler
        exc.solution = data.solution
        exc.resolved_at = datetime.now()
        await exc.save()

        if exc.wo_code and WorkOrder is not None:
            wo = await WorkOrder.filter(wo_code=exc.wo_code).first()
            if wo and wo.status == "suspended" and wo.suspend_reason == "exception":
                wo.status = "processing"
                wo.suspend_reason = None
                wo.suspend_source = None
                wo.suspended_at = None
                await wo.save()

        return exc

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        exception_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        work_center_code: Optional[str] = None
    ) -> Tuple[List[ProductionException], int]:
        query = ProductionException.all()
        if exception_type:
            query = query.filter(exception_type=exception_type)
        if severity:
            query = query.filter(severity=severity)
        if status:
            query = query.filter(status=status)
        if work_center_code:
            query = query.filter(work_center_code=work_center_code)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total


class ToolingService:
    model = "tooling"
    @staticmethod
    async def create_tooling(data: ToolingCreate) -> Tooling:
        existing = await Tooling.filter(tooling_code=data.tooling_code).first()
        if existing:
            raise ValueError(f"工装编码{data.tooling_code}已存在")
        return await Tooling.create(**data.model_dump())

    @staticmethod
    async def validate_tooling(tooling_code: str) -> Dict[str, Any]:
        tooling = await Tooling.filter(tooling_code=tooling_code).first()
        if not tooling:
            return {"tooling_code": tooling_code, "is_valid": False, "reason": "工装不存在"}
        if tooling.status == "scrapped":
            return {"tooling_code": tooling_code, "is_valid": False, "reason": "工装已报废"}
        if tooling.life_count and tooling.used_count >= tooling.life_count:
            return {"tooling_code": tooling_code, "is_valid": False, "reason": "工装已超过使用寿命"}
        if tooling.next_calibration_date and tooling.next_calibration_date < date.today():
            return {"tooling_code": tooling_code, "is_valid": False, "reason": "量具校准已过期"}
        return {"tooling_code": tooling_code, "is_valid": True, "reason": None}

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        tooling_code: Optional[str] = None,
        tooling_type: Optional[str] = None,
        status: Optional[str] = None,
        work_center_code: Optional[str] = None
    ) -> Tuple[List[Tooling], int]:
        query = Tooling.all()
        if tooling_code:
            query = query.filter(tooling_code__icontains=tooling_code)
        if tooling_type:
            query = query.filter(tooling_type=tooling_type)
        if status:
            query = query.filter(status=status)
        if work_center_code:
            query = query.filter(work_center_code=work_center_code)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total


class EnergyService:
    model = "energy"
    @staticmethod
    async def record_energy(data: EnergyRecordCreate) -> EnergyRecord:
        return await EnergyRecord.create(**data.model_dump())

    @staticmethod
    async def get_statistics(
        work_center_code: Optional[str] = None,
        energy_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        query = EnergyRecord.all()
        if work_center_code:
            query = query.filter(work_center_code=work_center_code)
        if energy_type:
            query = query.filter(energy_type=energy_type)

        records = await query.order_by('-record_time')
        total_consumption = sum(float(r.consumption_value) for r in records)

        return {
            "total_consumption": total_consumption,
            "unit_product_consumption": 0.0,
            "records": [await r.to_dict() for r in records[:100]]
        }