from fastapi import APIRouter

from .location_router import router as location_router
from .warehouse_router import router as warehouse_router
from .picking_type_router import router as picking_type_router
from .picking_router import router as picking_router
from .quant_router import router as quant_router
from .lot_router import router as lot_router
from .package_router import router as package_router

router = APIRouter(prefix="/v1/inventory", tags=["库存管理"])

router.include_router(location_router)
router.include_router(warehouse_router)
router.include_router(picking_type_router)
router.include_router(picking_router)
router.include_router(quant_router)
router.include_router(lot_router)
router.include_router(package_router)

__all__ = ["router"]