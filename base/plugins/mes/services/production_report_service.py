from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
try:
    from base.plugins.mes.models.production import WorkOrder, ManufacturingOrder
    from base.plugins.mes.models.production_report import ProductionReport
    from base.plugins.mes.models.trace import TraceRecord
    from base.plugins.mes.schemas.production_report_schema import (
        ProductionReportCreate, BatchReportRequest
    )
    try:
        from base.plugins.equipment.models.equipment import Equipment
        EQUIPMENT_AVAILABLE = True
    except ImportError:
        Equipment = None
        EQUIPMENT_AVAILABLE = False
except ImportError:
    ProductionReport = None
    WorkOrder = None
    ManufacturingOrder = None
    EQUIPMENT_AVAILABLE = False


class ProductionReportService:
    model = "production_report"
    @staticmethod
    async def submit_report(data: ProductionReportCreate, operator: str = None) -> ProductionReport:
        wo = await WorkOrder.filter(wo_code=data.wo_code).first()
        if not wo:
            raise ValueError(f"工单{data.wo_code}不存在")
        if wo.status not in ("released", "processing"):
            raise ValueError(f"工单当前状态为{wo.status}，无法报工")

        total_reported = wo.actual_quantity + wo.scrap_quantity + data.qualified_quantity + data.scrap_quantity
        if total_reported > wo.quantity:
            raise ValueError(f"报工数量超出计划数量，计划{wo.quantity}，已报{wo.actual_quantity + wo.scrap_quantity}，本次{data.qualified_quantity + data.scrap_quantity}")

        if EQUIPMENT_AVAILABLE and Equipment is not None:
            equip = await Equipment.filter(equipment_code=data.equipment_code).first()
            if equip and equip.status not in ("idle", "running"):
                raise ValueError(f"设备{data.equipment_code}状态为{equip.status}，无法报工")

        existing = await ProductionReport.filter(
            wo_code=data.wo_code,
            operator=data.operator,
            actual_start_time__gte=data.actual_start_time - timedelta(minutes=1),
            actual_end_time__lte=data.actual_end_time + timedelta(minutes=1)
        ).exists()
        if existing:
            raise ValueError("该工单在此时间段已有报工记录，请勿重复提交")

        work_hours = (data.actual_end_time - data.actual_start_time).total_seconds() / 60

        report_code = f"RPT{datetime.now().strftime('%Y%m%d%H%M%S')}"
        report = await ProductionReport.create(
            report_code=report_code,
            wo_code=data.wo_code,
            mo_code=data.mo_code,
            process_code=data.process_code,
            work_center_code=data.work_center_code,
            operator=data.operator or operator,
            shift_code=data.shift_code,
            equipment_code=data.equipment_code,
            batch_no=data.batch_no,
            qualified_quantity=data.qualified_quantity,
            scrap_quantity=data.scrap_quantity,
            actual_start_time=data.actual_start_time,
            actual_end_time=data.actual_end_time,
            actual_work_hours=round(work_hours, 2),
            remark=data.remark
        )

        wo.actual_quantity += data.qualified_quantity
        wo.scrap_quantity += data.scrap_quantity
        if wo.status == "released":
            wo.status = "processing"
        await wo.save()

        await TraceRecord.create(
            trace_code=f"TRC{datetime.now().strftime('%Y%m%d%H%M%S')}",
            trace_type="production",
            product_batch_no=data.batch_no,
            material_batch_no=data.batch_no,
            mo_code=data.mo_code,
            wo_code=data.wo_code,
            process_code=data.process_code,
            operator=data.operator or operator,
            equipment_code=data.equipment_code,
            work_center_code=data.work_center_code,
            shift_code=data.shift_code,
            consumed_quantity=Decimal(str(data.qualified_quantity + data.scrap_quantity)),
            produced_quantity=data.qualified_quantity
        )

        return report

    @staticmethod
    async def batch_report(data: BatchReportRequest, operator: str = None) -> dict:
        success_count = 0
        fail_count = 0
        results = []
        for report_data in data.reports:
            try:
                report = await ProductionReportService.submit_report(report_data, operator)
                results.append(report)
                success_count += 1
            except Exception as e:
                fail_count += 1
        return {
            "total": len(data.reports),
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results
        }

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        wo_code: Optional[str] = None,
        mo_code: Optional[str] = None,
        operator: Optional[str] = None,
        batch_no: Optional[str] = None,
        work_center_code: Optional[str] = None
    ) -> Tuple[List[ProductionReport], int]:
        query = ProductionReport.all()
        if wo_code:
            query = query.filter(wo_code=wo_code)
        if mo_code:
            query = query.filter(mo_code=mo_code)
        if operator:
            query = query.filter(operator=operator)
        if batch_no:
            query = query.filter(batch_no=batch_no)
        if work_center_code:
            query = query.filter(work_center_code=work_center_code)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total