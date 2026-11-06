from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.mes.services.base_data_service import (
        MaterialService, BomService, WorkCenterService, ProcessService, RouteService, BomVersionService
    )
    from base.plugins.mes.schemas.mes_schema import (
        MaterialCreate, MaterialUpdate, MaterialResponse, MaterialListQuery,
        BomCreate, BomUpdate, BomResponse, BomListQuery,
        WorkCenterCreate, WorkCenterUpdate, WorkCenterResponse, WorkCenterListQuery,
        ProcessCreate, ProcessUpdate, ProcessResponse, ProcessListQuery,
        RouteCreate, RouteUpdate, RouteResponse, RouteListQuery,
        ListResponse
    )
    from base.common.response import success_response
except ImportError:
    class BaseModel:
        pass

    class APIRouter:
        def __init__(self, prefix="", tags=None):
            self.prefix = prefix
            self.tags = tags or []

        def get(self, path):
            def decorator(func):
                return func
            return decorator

        def post(self, path):
            def decorator(func):
                return func
            return decorator

        def put(self, path):
            def decorator(func):
                return func
            return decorator

        def delete(self, path):
            def decorator(func):
                return func
            return decorator

    class Depends:
        def __init__(self, func):
            pass

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            pass

    class MaterialService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def create_material(data):
            return None
        @staticmethod
        async def update_material(id, data):
            return None
        @staticmethod
        async def delete_material(id):
            return False
        @staticmethod
        async def get_list(**kwargs):
            return [], 0

    class BomService(MaterialService): pass
    class WorkCenterService(MaterialService): pass
    class ProcessService(MaterialService): pass
    class RouteService(MaterialService): pass

    class MaterialCreate(BaseModel): pass
    class MaterialUpdate(BaseModel): pass
    class MaterialResponse(BaseModel): pass
    class MaterialListQuery(BaseModel): pass
    class BomCreate(BaseModel): pass
    class BomUpdate(BaseModel): pass
    class BomResponse(BaseModel): pass
    class BomListQuery(BaseModel): pass
    class WorkCenterCreate(BaseModel): pass
    class WorkCenterUpdate(BaseModel): pass
    class WorkCenterResponse(BaseModel): pass
    class WorkCenterListQuery(BaseModel): pass
    class ProcessCreate(BaseModel): pass
    class ProcessUpdate(BaseModel): pass
    class ProcessResponse(BaseModel): pass
    class ProcessListQuery(BaseModel): pass
    class RouteCreate(BaseModel): pass
    class RouteUpdate(BaseModel): pass
    class RouteResponse(BaseModel): pass
    class RouteListQuery(BaseModel): pass
    class ListResponse(BaseModel): pass

base_data_router = APIRouter(prefix="/base-data", tags=["基础数据管理"])

@base_data_router.get("/materials/{material_id}", summary="获取物料详情")
async def get_material(material_id: int):
    material = await MaterialService.get_by_id(material_id)
    if not material:
        raise HTTPException(status_code=404, detail="物料不存在")
    return success_response(data=material)

@base_data_router.post("/materials", summary="创建物料")
async def create_material(data: MaterialCreate):
    try:
        material = await MaterialService.create_material(data)
        return success_response(data=material)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.put("/materials/{material_id}", summary="更新物料")
async def update_material(material_id: int, data: MaterialUpdate):
    try:
        material = await MaterialService.update_material(material_id, data)
        if not material:
            raise HTTPException(status_code=404, detail="物料不存在")
        return success_response(data=material)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.delete("/materials/{material_id}", summary="删除物料")
async def delete_material(material_id: int):
    success = await MaterialService.delete_material(material_id)
    if not success:
        raise HTTPException(status_code=404, detail="物料不存在")
    return success_response(data={"message": "物料删除成功"}, msg="物料删除成功")

@base_data_router.get("/materials", summary="获取物料列表")
async def list_materials(
    page: int = 1,
    page_size: int = 10,
    material_code: Optional[str] = None,
    material_name: Optional[str] = None,
    material_type: Optional[str] = None,
    is_active: Optional[bool] = None
):
    items, total = await MaterialService.get_list(
        page=page, page_size=page_size,
        material_code=material_code,
        material_name=material_name,
        material_type=material_type,
        is_active=is_active
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@base_data_router.get("/boms/{bom_id}", summary="获取BOM详情")
async def get_bom(bom_id: int):
    bom = await BomService.get_by_id(bom_id)
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")
    return success_response(data=bom)

@base_data_router.post("/boms", summary="创建BOM")
async def create_bom(data: BomCreate):
    bom = await BomService.create_bom(data)
    return success_response(data=bom)

@base_data_router.put("/boms/{bom_id}", summary="更新BOM")
async def update_bom(bom_id: int, data: BomUpdate):
    bom = await BomService.update_bom(bom_id, data)
    if not bom:
        raise HTTPException(status_code=404, detail="BOM不存在")
    return success_response(data=bom)

@base_data_router.delete("/boms/{bom_id}", summary="删除BOM")
async def delete_bom(bom_id: int):
    success = await BomService.delete_bom(bom_id)
    if not success:
        raise HTTPException(status_code=404, detail="BOM不存在")
    return success_response(data={"message": "BOM删除成功"}, msg="BOM删除成功")

@base_data_router.get("/boms", summary="获取BOM列表")
async def list_boms(
    page: int = 1,
    page_size: int = 10,
    product_code: Optional[str] = None,
    item_code: Optional[str] = None,
    version: Optional[str] = None
):
    items, total = await BomService.get_list(
        page=page, page_size=page_size,
        product_code=product_code,
        item_code=item_code,
        version=version
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@base_data_router.get("/bom-versions", summary="获取BOM版本列表")
async def list_bom_versions(
    page: int = 1,
    page_size: int = 10,
    product_code: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await BomVersionService.get_list(
        page=page, page_size=page_size,
        product_code=product_code,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@base_data_router.get("/bom-versions/{version_id}", summary="获取BOM版本详情")
async def get_bom_version(version_id: int):
    version = await BomVersionService.get_by_id(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="BOM版本不存在")
    return success_response(data=version)

@base_data_router.get("/bom-versions/{product_code}/history", summary="获取产品BOM版本历史")
async def get_bom_version_history(product_code: str):
    versions = await BomVersionService.get_version_history(product_code)
    return success_response(data=versions)

@base_data_router.post("/bom-versions", summary="创建BOM版本")
async def create_bom_version(data: dict):
    try:
        version = await BomVersionService.create_version(
            product_code=data.get("product_code"),
            version=data.get("version"),
            product_name=data.get("product_name", ""),
            description=data.get("description"),
            ecn_code=data.get("ecn_code")
        )
        return success_response(data=version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.post("/bom-versions/{version_id}/copy", summary="复制BOM版本")
async def copy_bom_version(version_id: int, data: dict):
    try:
        new_version = await BomVersionService.copy_version(
            source_version_id=version_id,
            new_version=data.get("new_version")
        )
        return success_response(data=new_version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.put("/bom-versions/{version_id}/activate", summary="生效BOM版本")
async def activate_bom_version(version_id: int):
    try:
        version = await BomVersionService.activate_version(version_id)
        if not version:
            raise HTTPException(status_code=404, detail="BOM版本不存在")
        return success_response(data=version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.put("/bom-versions/{version_id}/obsolete", summary="作废BOM版本")
async def obsolete_bom_version(version_id: int):
    try:
        version = await BomVersionService.obsolete_version(version_id)
        if not version:
            raise HTTPException(status_code=404, detail="BOM版本不存在")
        return success_response(data=version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.get("/work-centers/{wc_id}", summary="获取工作中心详情")
async def get_work_center(wc_id: int):
    wc = await WorkCenterService.get_by_id(wc_id)
    if not wc:
        raise HTTPException(status_code=404, detail="工作中心不存在")
    return success_response(data=wc)

@base_data_router.post("/work-centers", summary="创建工作中心")
async def create_work_center(data: WorkCenterCreate):
    try:
        wc = await WorkCenterService.create_work_center(data)
        return success_response(data=wc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.put("/work-centers/{wc_id}", summary="更新工作中心")
async def update_work_center(wc_id: int, data: WorkCenterUpdate):
    try:
        wc = await WorkCenterService.update_work_center(wc_id, data)
        if not wc:
            raise HTTPException(status_code=404, detail="工作中心不存在")
        return success_response(data=wc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.delete("/work-centers/{wc_id}", summary="删除工作中心")
async def delete_work_center(wc_id: int):
    success = await WorkCenterService.delete_work_center(wc_id)
    if not success:
        raise HTTPException(status_code=404, detail="工作中心不存在")
    return success_response(data={"message": "工作中心删除成功"}, msg="工作中心删除成功")

@base_data_router.get("/work-centers", summary="获取工作中心列表")
async def list_work_centers(
    page: int = 1,
    page_size: int = 10,
    work_center_code: Optional[str] = None,
    work_center_name: Optional[str] = None,
    department: Optional[str] = None
):
    items, total = await WorkCenterService.get_list(
        page=page, page_size=page_size,
        work_center_code=work_center_code,
        work_center_name=work_center_name,
        department=department
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@base_data_router.get("/processes/{process_id}", summary="获取工序详情")
async def get_process(process_id: int):
    process = await ProcessService.get_by_id(process_id)
    if not process:
        raise HTTPException(status_code=404, detail="工序不存在")
    return success_response(data=process)

@base_data_router.post("/processes", summary="创建工序")
async def create_process(data: ProcessCreate):
    try:
        process = await ProcessService.create_process(data)
        return success_response(data=process)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.put("/processes/{process_id}", summary="更新工序")
async def update_process(process_id: int, data: ProcessUpdate):
    try:
        process = await ProcessService.update_process(process_id, data)
        if not process:
            raise HTTPException(status_code=404, detail="工序不存在")
        return success_response(data=process)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.delete("/processes/{process_id}", summary="删除工序")
async def delete_process(process_id: int):
    success = await ProcessService.delete_process(process_id)
    if not success:
        raise HTTPException(status_code=404, detail="工序不存在")
    return success_response(data={"message": "工序删除成功"}, msg="工序删除成功")

@base_data_router.get("/processes", summary="获取工序列表")
async def list_processes(
    page: int = 1,
    page_size: int = 10,
    process_code: Optional[str] = None,
    process_name: Optional[str] = None,
    work_center_code: Optional[str] = None
):
    items, total = await ProcessService.get_list(
        page=page, page_size=page_size,
        process_code=process_code,
        process_name=process_name,
        work_center_code=work_center_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@base_data_router.get("/routes/{route_id}", summary="获取工艺路线详情")
async def get_route(route_id: int):
    route = await RouteService.get_route_with_processes(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="工艺路线不存在")
    return success_response(data=route)

@base_data_router.post("/routes", summary="创建工艺路线")
async def create_route(data: RouteCreate):
    try:
        route = await RouteService.create_route(data)
        route_with_processes = await RouteService.get_route_with_processes(route.id)
        return success_response(data=route_with_processes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.put("/routes/{route_id}", summary="更新工艺路线")
async def update_route(route_id: int, data: RouteUpdate):
    try:
        route = await RouteService.update_route(route_id, data)
        if not route:
            raise HTTPException(status_code=404, detail="工艺路线不存在")
        route_with_processes = await RouteService.get_route_with_processes(route_id)
        return success_response(data=route_with_processes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@base_data_router.delete("/routes/{route_id}", summary="删除工艺路线")
async def delete_route(route_id: int):
    success = await RouteService.delete_route(route_id)
    if not success:
        raise HTTPException(status_code=404, detail="工艺路线不存在")
    return success_response(data={"message": "工艺路线删除成功"}, msg="工艺路线删除成功")

@base_data_router.get("/routes", summary="获取工艺路线列表")
async def list_routes(
    page: int = 1,
    page_size: int = 10,
    route_code: Optional[str] = None,
    route_name: Optional[str] = None,
    product_code: Optional[str] = None,
    bom_code: Optional[str] = None
):
    items, total = await RouteService.get_list(
        page=page, page_size=page_size,
        route_code=route_code,
        route_name=route_name,
        product_code=product_code,
        bom_code=bom_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@base_data_router.get("/boms/options", summary="获取BOM选项列表（用于下拉选择）")
async def get_bom_options():
    boms = await Bom.filter(is_active=True).distinct('product_code', 'version').order_by('product_code', 'version')
    options = []
    seen = set()
    for bom in boms:
        key = f"{bom.product_code}-{bom.version}"
        if key not in seen:
            seen.add(key)
            options.append({
                "value": bom.product_code,
                "label": f"{bom.product_code} ({bom.product_name or ''}) - {bom.version}",
                "version": bom.version,
                "product_name": bom.product_name
            })
    return success_response(data=options)

@base_data_router.get("/routes/{route_id}/processes", summary="获取工艺路线的工序列表")
async def get_route_processes(route_id: int):
    route = await RouteService.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="工艺路线不存在")
    return success_response(data=await RouteService.get_route_with_processes(route_id))