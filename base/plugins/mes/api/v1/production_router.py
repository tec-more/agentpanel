from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

try:
    from base.plugins.mes.services.production_service import (
        ManufacturingOrderService, WorkOrderService
    )
    from base.plugins.mes.schemas.mes_schema import (
        ManufacturingOrderCreate, ManufacturingOrderUpdate, ManufacturingOrderResponse, ManufacturingOrderListQuery,
        WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse, WorkOrderListQuery,
        StartWORequest, SuspendWORequest, ResumeWORequest,
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

    class ManufacturingOrderService:
        @staticmethod
        async def get_by_id(id):
            return None
        @staticmethod
        async def create_mo(data):
            return None
        @staticmethod
        async def update_mo(id, data):
            return None
        @staticmethod
        async def delete_mo(id):
            return False
        @staticmethod
        async def release_mo(id):
            return None
        @staticmethod
        async def complete_mo(id):
            return None
        @staticmethod
        async def cancel_mo(id):
            return None
        @staticmethod
        async def get_list(**kwargs):
            return [], 0

    class WorkOrderService(ManufacturingOrderService):
        @staticmethod
        async def create_wo(data):
            return None
        @staticmethod
        async def update_wo(id, data):
            return None
        @staticmethod
        async def delete_wo(id):
            return False
        @staticmethod
        async def release_wo(id):
            return None
        @staticmethod
        async def start_wo(id, operator=None):
            return None
        @staticmethod
        async def complete_wo(id, actual_qty, scrap_qty=0):
            return None
        @staticmethod
        async def close_wo(id):
            return None

    class WorkOrderCreate(BaseModel): pass
    class WorkOrderUpdate(BaseModel): pass
    class WorkOrderResponse(BaseModel): pass
    class WorkOrderListQuery(BaseModel): pass
    class ListResponse(BaseModel): pass

production_router = APIRouter(prefix="/production", tags=["生产计划管理"])

@production_router.get("/manufacturing-orders/{mo_id}", summary="获取制造单详情")
async def get_mo(mo_id: int):
    mo = await ManufacturingOrderService.get_by_id(mo_id)
    if not mo:
        raise HTTPException(status_code=404, detail="制造单不存在")
    return success_response(data=mo)

@production_router.post("/manufacturing-orders", summary="创建制造单")
async def create_mo(data: ManufacturingOrderCreate):
    try:
        mo = await ManufacturingOrderService.create_mo(data)
        return success_response(data=mo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.put("/manufacturing-orders/{mo_id}", summary="更新制造单")
async def update_mo(mo_id: int, data: ManufacturingOrderUpdate):
    try:
        mo = await ManufacturingOrderService.update_mo(mo_id, data)
        if not mo:
            raise HTTPException(status_code=404, detail="制造单不存在")
        return success_response(data=mo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.delete("/manufacturing-orders/{mo_id}", summary="删除制造单")
async def delete_mo(mo_id: int):
    success = await ManufacturingOrderService.delete_mo(mo_id)
    if not success:
        raise HTTPException(status_code=404, detail="制造单不存在")
    return success_response(data={"message": "制造单删除成功"}, msg="制造单删除成功")

@production_router.post("/manufacturing-orders/{mo_id}/release", summary="下发制造单")
async def release_mo(mo_id: int):
    try:
        mo = await ManufacturingOrderService.release_mo(mo_id)
        if not mo:
            raise HTTPException(status_code=404, detail="制造单不存在")
        return success_response(data=mo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/manufacturing-orders/{mo_id}/complete", summary="完成制造单")
async def complete_mo(mo_id: int):
    try:
        mo = await ManufacturingOrderService.complete_mo(mo_id)
        if not mo:
            raise HTTPException(status_code=404, detail="制造单不存在")
        return success_response(data=mo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/manufacturing-orders/{mo_id}/cancel", summary="取消制造单")
async def cancel_mo(mo_id: int):
    try:
        mo = await ManufacturingOrderService.cancel_mo(mo_id)
        if not mo:
            raise HTTPException(status_code=404, detail="制造单不存在")
        return success_response(data=mo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/manufacturing-orders/{mo_id}/generate-work-orders", summary="从制造单生成工单")
async def generate_work_orders(mo_id: int):
    try:
        work_orders = await ManufacturingOrderService.generate_work_orders(mo_id)
        return success_response(data={"work_orders": work_orders, "count": len(work_orders)})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.get("/manufacturing-orders", summary="获取制造单列表")
async def list_mos(
    page: int = 1,
    page_size: int = 10,
    mo_code: Optional[str] = None,
    product_code: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    items, total = await ManufacturingOrderService.get_list(
        page=page, page_size=page_size,
        mo_code=mo_code,
        product_code=product_code,
        status=status,
        priority=priority
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@production_router.get("/plans", summary="获取生产计划列表（制造单别名）")
async def list_plans(
    page: int = 1,
    page_size: int = 10,
    plan_code: Optional[str] = None,
    product_name: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    items, total = await ManufacturingOrderService.get_list(
        page=page, page_size=page_size,
        mo_code=plan_code,
        status=status,
        priority=priority
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@production_router.get("/work-orders/{wo_id}", summary="获取工单详情")
async def get_wo(wo_id: int):
    wo = await WorkOrderService.get_by_id(wo_id)
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success_response(data=wo)

@production_router.post("/work-orders", summary="创建工单")
async def create_wo(data: WorkOrderCreate):
    try:
        wo = await WorkOrderService.create_wo(data)
        return success_response(data=wo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.put("/work-orders/{wo_id}", summary="更新工单")
async def update_wo(wo_id: int, data: WorkOrderUpdate):
    try:
        wo = await WorkOrderService.update_wo(wo_id, data)
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        return success_response(data=wo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.delete("/work-orders/{wo_id}", summary="删除工单")
async def delete_wo(wo_id: int):
    success = await WorkOrderService.delete_wo(wo_id)
    if not success:
        raise HTTPException(status_code=404, detail="工单不存在")
    return success_response(data={"message": "工单删除成功"}, msg="工单删除成功")

@production_router.post("/work-orders/{wo_id}/release", summary="下发工单")
async def release_wo(wo_id: int):
    try:
        wo = await WorkOrderService.release_wo(wo_id)
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        return success_response(data=wo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/work-orders/{wo_id}/start", summary="开工工单")
async def start_wo(wo_id: int, data: StartWORequest):
    try:
        wo = await WorkOrderService.start_wo(wo_id, data)
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        return success_response(data=wo, msg="工单已开工")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/work-orders/{wo_id}/suspend", summary="暂停工单")
async def suspend_wo(wo_id: int, data: SuspendWORequest):
    try:
        wo = await WorkOrderService.suspend_wo(wo_id, data)
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        return success_response(data=wo, msg="工单已暂停")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/work-orders/{wo_id}/resume", summary="恢复工单")
async def resume_wo(wo_id: int, data: ResumeWORequest = None):
    try:
        wo = await WorkOrderService.resume_wo(wo_id, data)
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        return success_response(data=wo, msg="工单已恢复")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/work-orders/{wo_id}/complete", summary="完工工单")
async def complete_wo(wo_id: int, actual_quantity: int, scrap_quantity: int = 0):
    try:
        wo = await WorkOrderService.complete_wo(wo_id, actual_quantity, scrap_quantity)
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        return success_response(data=wo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.post("/work-orders/{wo_id}/close", summary="关闭工单")
async def close_wo(wo_id: int):
    try:
        wo = await WorkOrderService.close_wo(wo_id)
        if not wo:
            raise HTTPException(status_code=404, detail="工单不存在")
        return success_response(data=wo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_router.get("/work-orders", summary="获取工单列表")
async def list_wos(
    page: int = 1,
    page_size: int = 10,
    wo_code: Optional[str] = None,
    mo_code: Optional[str] = None,
    product_code: Optional[str] = None,
    status: Optional[str] = None,
    work_center_code: Optional[str] = None
):
    items, total = await WorkOrderService.get_list(
        page=page, page_size=page_size,
        wo_code=wo_code,
        mo_code=mo_code,
        product_code=product_code,
        status=status,
        work_center_code=work_center_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


@production_router.get("/orders", summary="获取生产订单列表（工单别名）")
async def list_orders(
    page: int = 1,
    page_size: int = 10,
    order_code: Optional[str] = None,
    product_name: Optional[str] = None,
    status: Optional[str] = None,
    work_center_code: Optional[str] = None
):
    items, total = await WorkOrderService.get_list(
        page=page, page_size=page_size,
        wo_code=order_code,
        status=status,
        work_center_code=work_center_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})