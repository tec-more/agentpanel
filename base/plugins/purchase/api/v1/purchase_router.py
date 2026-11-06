from fastapi import APIRouter, Query
from typing import Optional

from base.plugins.purchase.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderResponse,
    PurchaseReceiptCreate,
    PurchaseReceiptUpdate,
    PurchaseReceiptResponse
)
from base.plugins.purchase.services import PurchaseOrderService, PurchaseReceiptService

purchase_router = APIRouter(prefix="/order", tags=["采购-订单管理"])


@purchase_router.post("/", response_model=PurchaseOrderResponse, summary="创建采购订单")
async def create_purchase_order(data: PurchaseOrderCreate):
    order = await PurchaseOrderService.create(data.dict())
    return await order.to_dict()


@purchase_router.get("/{order_id}", response_model=PurchaseOrderResponse, summary="获取采购订单详情")
async def get_purchase_order(order_id: int):
    order = await PurchaseOrderService.get_purchase_order(order_id)
    if not order:
        return {"error": "采购订单不存在"}, 404
    return await order.to_dict()


@purchase_router.get("/", summary="获取采购订单列表")
async def get_purchase_order_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    order_no: Optional[str] = Query(None),
    supplier_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    return await PurchaseOrderService.get_purchase_order_list(
        page=page,
        page_size=page_size,
        order_no=order_no,
        supplier_name=supplier_name,
        status=status,
        start_date=start_date,
        end_date=end_date
    )


@purchase_router.put("/{order_id}", response_model=PurchaseOrderResponse, summary="更新采购订单")
async def update_purchase_order(order_id: int, data: PurchaseOrderUpdate):
    order = await PurchaseOrderService.update(order_id, data.dict())
    if not order:
        return {"error": "采购订单不存在"}, 404
    return await order.to_dict()


@purchase_router.post("/{order_id}/confirm", response_model=PurchaseOrderResponse, summary="确认采购订单")
async def confirm_purchase_order(order_id: int):
    order = await PurchaseOrderService.confirm_purchase_order(order_id)
    if not order:
        return {"error": "采购订单不存在或无法确认"}, 404
    return await order.to_dict()


@purchase_router.post("/{order_id}/cancel", response_model=PurchaseOrderResponse, summary="取消采购订单")
async def cancel_purchase_order(order_id: int):
    order = await PurchaseOrderService.cancel_purchase_order(order_id)
    if not order:
        return {"error": "采购订单不存在或无法取消"}, 404
    return await order.to_dict()


@purchase_router.delete("/{order_id}", summary="删除采购订单")
async def delete_purchase_order(order_id: int):
    success = await PurchaseOrderService.delete(order_id)
    if not success:
        return {"error": "采购订单不存在"}, 404
    return {"message": "删除成功"}


@purchase_router.post("/receipt/", response_model=PurchaseReceiptResponse, summary="创建采购收货单")
async def create_purchase_receipt(data: PurchaseReceiptCreate):
    try:
        receipt = await PurchaseReceiptService.create(data.dict())
        return await receipt.to_dict()
    except ValueError as e:
        return {"error": str(e)}, 400


@purchase_router.get("/receipt/{receipt_id}", response_model=PurchaseReceiptResponse, summary="获取采购收货单详情")
async def get_purchase_receipt(receipt_id: int):
    receipt = await PurchaseReceiptService.get_purchase_receipt(receipt_id)
    if not receipt:
        return {"error": "采购收货单不存在"}, 404
    return await receipt.to_dict()


@purchase_router.get("/receipt/", summary="获取采购收货单列表")
async def get_purchase_receipt_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    receipt_no: Optional[str] = Query(None),
    order_no: Optional[str] = Query(None),
    supplier_name: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None)
):
    return await PurchaseReceiptService.get_purchase_receipt_list(
        page=page,
        page_size=page_size,
        receipt_no=receipt_no,
        order_no=order_no,
        supplier_name=supplier_name,
        start_date=start_date,
        end_date=end_date
    )


@purchase_router.put("/receipt/{receipt_id}", response_model=PurchaseReceiptResponse, summary="更新采购收货单")
async def update_purchase_receipt(receipt_id: int, data: PurchaseReceiptUpdate):
    receipt = await PurchaseReceiptService.update(receipt_id, data.dict())
    if not receipt:
        return {"error": "采购收货单不存在"}, 404
    return await receipt.to_dict()


@purchase_router.delete("/receipt/{receipt_id}", summary="删除采购收货单")
async def delete_purchase_receipt(receipt_id: int):
    success = await PurchaseReceiptService.delete(receipt_id)
    if not success:
        return {"error": "采购收货单不存在"}, 404
    return {"message": "删除成功"}