from fastapi import APIRouter, Query
from typing import Optional
from base.plugins.subcontracting.services.subcontracting_transit_service import SubcontractingTransitService

subcontracting_transit_router = APIRouter(prefix="/transit", tags=["委外-在途库存"])


@subcontracting_transit_router.get("/", summary="查询委外在途库存")
async def get_transit_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    material_code: Optional[str] = Query(None),
    supplier_code: Optional[str] = Query(None),
):
    return await SubcontractingTransitService.get_transit_list(
        page=page, page_size=page_size,
        material_code=material_code, supplier_code=supplier_code
    )


@subcontracting_transit_router.get("/{material_code}", summary="查询指定物料在途库存")
async def get_transit_by_material(material_code: str):
    items = await SubcontractingTransitService.get_transit_by_material(material_code)
    return {"items": items, "total": len(items)}