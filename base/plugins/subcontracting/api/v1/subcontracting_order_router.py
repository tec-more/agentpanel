from fastapi import APIRouter, Query
from typing import Optional
from base.plugins.subcontracting.schemas.subcontracting_schema import (
    SubcontractingOrderCreate, SubcontractingOrderResponse, SubcontractingOrderListQuery
)
from base.plugins.subcontracting.services.subcontracting_order_service import SubcontractingOrderService

subcontracting_order_router = APIRouter(prefix="/orders", tags=["委外-工单管理"])


@subcontracting_order_router.post("/", summary="创建委外工单")
async def create_order(data: SubcontractingOrderCreate):
    try:
        order = await SubcontractingOrderService.create_order(data.dict())
        result = await order.to_dict()
        from base.plugins.subcontracting.services.subcontracting_order_service import STATUS_LABELS
        result["status_label"] = STATUS_LABELS.get(order.status, order.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_order_router.get("/", summary="查询委外工单列表")
async def get_order_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    status: Optional[str] = Query(None),
    supplier_code: Optional[str] = Query(None),
    product_code: Optional[str] = Query(None),
):
    return await SubcontractingOrderService.get_list(
        page=page, page_size=page_size, status=status,
        supplier_code=supplier_code, product_code=product_code
    )


@subcontracting_order_router.get("/{order_id}", summary="获取委外工单详情")
async def get_order(order_id: int):
    order = await SubcontractingOrderService.get_by_id(order_id)
    if not order:
        return {"error": "委外工单不存在"}
    result = await order.to_dict()
    from base.plugins.subcontracting.services.subcontracting_order_service import STATUS_LABELS
    result["status_label"] = STATUS_LABELS.get(order.status, order.status)
    return result


@subcontracting_order_router.put("/{order_id}/release", summary="下发委外工单")
async def release_order(order_id: int):
    try:
        order = await SubcontractingOrderService.release_order(order_id)
        result = await order.to_dict()
        from base.plugins.subcontracting.services.subcontracting_order_service import STATUS_LABELS
        result["status_label"] = STATUS_LABELS.get(order.status, order.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_order_router.put("/{order_id}/cancel", summary="取消委外工单")
async def cancel_order(order_id: int):
    try:
        order = await SubcontractingOrderService.cancel_order(order_id)
        result = await order.to_dict()
        from base.plugins.subcontracting.services.subcontracting_order_service import STATUS_LABELS
        result["status_label"] = STATUS_LABELS.get(order.status, order.status)
        return result
    except ValueError as e:
        return {"error": str(e)}