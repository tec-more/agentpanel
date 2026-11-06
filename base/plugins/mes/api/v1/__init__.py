from fastapi import APIRouter

from .base_data_router import base_data_router
from .production_router import production_router
from .production_report_router import production_report_router
from .material_flow_router import material_requisition_router, material_return_router, production_receipt_router
from .mes_support_router import trace_router, dashboard_router, barcode_router, shift_router, exception_router, tooling_router, energy_router
from .kit_check_router import kit_check_router

router = APIRouter(prefix="/v1/mes")

router.include_router(base_data_router)
router.include_router(production_router)
router.include_router(production_report_router)
router.include_router(material_requisition_router)
router.include_router(material_return_router)
router.include_router(production_receipt_router)
router.include_router(trace_router)
router.include_router(dashboard_router)
router.include_router(barcode_router)
router.include_router(shift_router)
router.include_router(exception_router)
router.include_router(tooling_router)
router.include_router(energy_router)
router.include_router(kit_check_router)

__all__ = ["router"]