from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from base.common.response import SuccessResponse
from base.plugins.sales.schemas.order_schema import (
    CreateOrderIn, OrderOut, OrderListResponse, OrderUpdateRequest,
    OrderCreateResponse
)
from base.plugins.sales.services.order_service import OrderService

order_router = APIRouter(prefix="/orders", tags=["订单管理"])


@order_router.post("/create", response_model=OrderCreateResponse, summary="创建订单")
async def create_order(order_create: CreateOrderIn):
    try:
        items_data = [item.model_dump() for item in order_create.items]
        order = await OrderService.create_order(
            customer_id=order_create.customer_id,
            items=items_data,
            payment_method=order_create.payment_method,
            client_ip=order_create.client_ip,
            device_info=order_create.device_info,
            remark=order_create.remark
        )

        return SuccessResponse(
            data={
                "order_id": order.id,
                "order_no": order.order_no,
                "total_amount": float(order.total_amount),
                "final_amount": float(order.final_amount)
            },
            msg="订单创建成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="创建订单失败")


@order_router.post("/create-membership", response_model=OrderCreateResponse, summary="创建会员充值订单")
async def create_membership_order(
    customer_id: int,
    membership_level_id: int,
    payment_method: str,
    client_ip: Optional[str] = None
):
    try:
        order = await OrderService.create_membership_order(
            customer_id=customer_id,
            membership_level_id=membership_level_id,
            payment_method=payment_method,
            client_ip=client_ip
        )

        return SuccessResponse(
            data={
                "order_id": order.id,
                "order_no": order.order_no,
                "total_amount": float(order.total_amount),
                "final_amount": float(order.final_amount)
            },
            msg="订单创建成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="创建订单失败")


@order_router.get("/by-order-no/{order_no}", response_model=OrderOut, summary="根据订单号获取订单详情")
async def get_order_by_no(order_no: str):
    await OrderService.check_and_cancel_expired_order(order_no)

    order = await OrderService.get_order_by_no(order_no)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if hasattr(order, 'to_dict'):
        order_dict = await order.to_dict()
    elif hasattr(order, 'dict'):
        order_dict = order.dict()
    else:
        order_dict = dict(order)

    return SuccessResponse(data=order_dict, msg="获取订单详情成功")


@order_router.get("/customer/{customer_id}", response_model=OrderListResponse, summary="获取客户订单列表")
async def get_customer_orders(
        customer_id: int,
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=2000, description="每页数量")
):
    orders = await OrderService.get_orders_by_customer(customer_id, page, page_size)

    from base.plugins.sales.models.order import CustomerOrder, OrderItem
    total = await CustomerOrder.filter(customer_id=customer_id).count()

    order_list = []
    for order in orders:
        items = await OrderItem.filter(order_id=order.id)

        product_summary = []
        for item in items:
            product_summary.append(f"{item.product_name} x{item.quantity}")

        order_data = {
            "id": order.id,
            "order_no": order.order_no,
            "customer_id": order.customer_id,
            "customer_name": str(order.customer) if order.customer else None,
            "total_amount": float(order.total_amount),
            "final_amount": float(order.final_amount),
            "payment_method": order.payment_method.value if hasattr(order.payment_method, 'value') else order.payment_method,
            "payment_status": order.payment_status.value if hasattr(order.payment_status, 'value') else order.payment_status,
            "order_status": order.order_status.value if hasattr(order.order_status, 'value') else order.order_status,
            "pay_time": order.pay_time.strftime("%Y-%m-%d %H:%M:%S") if order.pay_time else None,
            "expire_time": order.expire_time.strftime("%Y-%m-%d %H:%M:%S") if order.expire_time else None,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else None,
            "product_summary": product_summary,
            "item_count": len(items),
            "first_product_name": items[0].product_name if items else None,
            "first_product_image": items[0].product_image if items else None,
        }
        order_list.append(order_data)

    return SuccessResponse(data={"total": total, "items": order_list}, msg="获取客户订单列表成功")


@order_router.get("/", response_model=OrderListResponse, summary="获取所有订单列表")
async def get_all_orders(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=2000, description="每页数量"),
    order_no: Optional[str] = Query(None, description="订单号"),
    customer_name: Optional[str] = Query(None, description="客户名称"),
    product_name: Optional[str] = Query(None, description="产品名称"),
    order_status: Optional[str] = Query(None, description="订单状态"),
    payment_status: Optional[str] = Query(None, description="支付状态")
):
    orders = await OrderService.get_all_orders(page, page_size, order_status=order_status, payment_status=payment_status)

    from base.plugins.sales.models.order import CustomerOrder, OrderItem
    query = CustomerOrder.all()
    if order_status:
        query = query.filter(order_status=order_status)
    if payment_status:
        query = query.filter(payment_status=payment_status)
    total = await query.count()

    order_list = []
    for order in orders:
        items = await OrderItem.filter(order_id=order.id)

        product_summary = []
        for item in items:
            product_summary.append(f"{item.product_name} x{item.quantity}")

        order_data = {
            "id": order.id,
            "order_no": order.order_no,
            "customer_id": order.customer_id,
            "customer_name": str(order.customer) if order.customer else None,
            "total_amount": float(order.total_amount),
            "final_amount": float(order.final_amount),
            "payment_method": order.payment_method.value if hasattr(order.payment_method, 'value') else order.payment_method,
            "payment_status": order.payment_status.value if hasattr(order.payment_status, 'value') else order.payment_status,
            "order_status": order.order_status.value if hasattr(order.order_status, 'value') else order.order_status,
            "pay_time": order.pay_time.strftime("%Y-%m-%d %H:%M:%S") if order.pay_time else None,
            "expire_time": order.expire_time.strftime("%Y-%m-%d %H:%M:%S") if order.expire_time else None,
            "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else None,
            "product_summary": product_summary,
            "item_count": len(items),
            "first_product_name": items[0].product_name if items else None,
            "first_product_image": items[0].product_image if items else None,
        }
        order_list.append(order_data)

    return SuccessResponse(data={"total": total, "items": order_list}, msg="获取所有订单列表成功")


@order_router.get("/list", response_model=OrderListResponse, summary="获取所有订单列表(别名路由)")
async def get_all_orders_alias(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=2000, description="每页数量"),
    order_no: Optional[str] = Query(None, description="订单号"),
    customer_name: Optional[str] = Query(None, description="客户名称"),
    product_name: Optional[str] = Query(None, description="产品名称"),
    order_status: Optional[str] = Query(None, description="订单状态"),
    payment_status: Optional[str] = Query(None, description="支付状态")
):
    return await get_all_orders(page=page, page_size=page_size, order_no=order_no, customer_name=customer_name, product_name=product_name, order_status=order_status, payment_status=payment_status)


@order_router.delete("/batch", summary="批量删除订单")
async def batch_delete_order(request_data: dict):
    try:
        from base.plugins.sales.models.order import CustomerOrder, OrderItem

        ids = request_data.get("ids", [])
        if not ids:
            raise HTTPException(status_code=400, detail="请选择要删除的订单")

        success_count = 0
        for order_id in ids:
            await OrderItem.filter(order_id=order_id).delete()
            result = await CustomerOrder.filter(id=order_id).delete()
            if result > 0:
                success_count += 1

        return SuccessResponse(data={"deleted": success_count, "total": len(ids)}, msg=f"成功删除{success_count}/{len(ids)}个订单")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="批量删除订单失败")


@order_router.get("/{order_id}", response_model=OrderOut, summary="获取订单详情")
async def get_order(order_id: int):
    order = await OrderService.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    await OrderService.check_and_cancel_expired_order(order.order_no)

    order = await OrderService.get_order_by_id(order_id)

    if hasattr(order, 'to_dict'):
        order_dict = await order.to_dict()
    elif hasattr(order, 'dict'):
        order_dict = order.dict()
    else:
        order_dict = dict(order)

    return SuccessResponse(data=order_dict, msg="获取订单详情成功")


@order_router.put("/{order_id}", response_model=OrderOut, summary="更新订单信息")
async def update_order(order_id: int, order_update: OrderUpdateRequest):
    order = await OrderService.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    update_data = order_update.model_dump(exclude_unset=True)

    if "payment_status" in update_data:
        success = await OrderService.update_payment_status(
            order_id=order_id,
            status=update_data["payment_status"]
        )
        if not success:
            raise HTTPException(status_code=500, detail="更新支付状态失败")

    if "remark" in update_data:
        from base.plugins.sales.models.order import CustomerOrder
        await CustomerOrder.filter(id=order_id).update(remark=update_data["remark"])

    updated_order = await OrderService.get_order_by_id(order_id)

    if hasattr(updated_order, 'to_dict'):
        order_dict = await updated_order.to_dict()
    elif hasattr(updated_order, 'dict'):
        order_dict = updated_order.dict()
    else:
        order_dict = dict(updated_order)

    return SuccessResponse(data=order_dict, msg="更新订单信息成功")


@order_router.delete("/{order_id}", summary="删除订单")
async def delete_order(order_id: int):
    try:
        from base.plugins.sales.models.order import CustomerOrder, OrderItem

        order = await CustomerOrder.get_or_none(id=order_id)
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        await OrderItem.filter(order_id=order_id).delete()
        await order.delete()

        return SuccessResponse(msg="订单删除成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="删除订单失败")


@order_router.patch("/{order_id}/status", summary="更新订单状态")
async def update_order_status_only(order_id: int, status_data: dict):
    try:
        order = await OrderService.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        status = status_data.get("status")
        if status:
            success = await OrderService.update_order_status(order_id, status)
            if not success:
                raise HTTPException(status_code=500, detail="更新订单状态失败")

        updated_order = await OrderService.get_order_by_id(order_id)

        if hasattr(updated_order, 'to_dict'):
            order_dict = await updated_order.to_dict()
        elif hasattr(updated_order, 'dict'):
            order_dict = updated_order.dict()
        else:
            order_dict = dict(updated_order)

        return SuccessResponse(data=order_dict, msg="订单状态更新成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="更新订单状态失败")


@order_router.patch("/{order_id}/payment-status", summary="更新支付状态")
async def update_payment_status_only(order_id: int, payment_data: dict):
    try:
        order = await OrderService.get_order_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        status = payment_data.get("payment_status")
        if status is not None:
            success = await OrderService.update_payment_status(
                order_id=order_id,
                status=status,
                payment_method=payment_data.get("payment_method"),
                transaction_id=payment_data.get("transaction_id")
            )
            if not success:
                raise HTTPException(status_code=500, detail="更新支付状态失败")

        updated_order = await OrderService.get_order_by_id(order_id)

        if hasattr(updated_order, 'to_dict'):
            order_dict = await updated_order.to_dict()
        elif hasattr(updated_order, 'dict'):
            order_dict = updated_order.dict()
        else:
            order_dict = dict(updated_order)

        return SuccessResponse(data=order_dict, msg="支付状态更新成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="更新支付状态失败")
