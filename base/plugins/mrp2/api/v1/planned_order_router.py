from typing import Optional
from fastapi import APIRouter, HTTPException

from base.plugins.mrp2.services.planned_order_service import PlannedOrderService
from base.plugins.mrp2.schemas.planned_order_schema import PlannedOrderConfirmRequest
from base.common.response import success_response

planned_order_router = APIRouter(prefix="/planned-order", tags=["计划订单"])

@planned_order_router.get("", summary="获取计划订单列表")
async def list_planned_orders(
    page: int = 1,
    page_size: int = 10,
    mrp_id: Optional[int] = None,
    order_type: Optional[str] = None,
    material_code: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await PlannedOrderService.get_list(
        page=page, page_size=page_size,
        mrp_id=mrp_id,
        order_type=order_type,
        material_code=material_code,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@planned_order_router.get("/{order_id}", summary="获取计划订单详情")
async def get_planned_order(order_id: int):
    order = await PlannedOrderService.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="计划订单不存在")
    return success_response(data=order)

@planned_order_router.post("/{order_id}/confirm", summary="确认计划订单")
async def confirm_planned_order(order_id: int, data: PlannedOrderConfirmRequest = None):
    try:
        order = await PlannedOrderService.confirm_order(order_id, data)
        if not order:
            raise HTTPException(status_code=404, detail="计划订单不存在")
        return success_response(data=order, msg="计划订单已确认")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@planned_order_router.post("/{order_id}/cancel", summary="取消计划订单")
async def cancel_planned_order(order_id: int):
    try:
        order = await PlannedOrderService.cancel_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="计划订单不存在")
        return success_response(data=order, msg="计划订单已取消")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))