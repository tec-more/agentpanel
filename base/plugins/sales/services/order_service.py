from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from tortoise.transactions import atomic
from decimal import Decimal
from loguru import logger

try:
    from base.common.events.event_bus import event_bus
except ImportError:
    event_bus = None

try:
    from base.plugins.sales.models.order import (
        CustomerOrder, OrderItem, OrderStatus, PaymentStatus, PaymentMethod, generate_order_no
    )
    from base.plugins.customer.models.customer import Customer
    from base.plugins.customer.models.customer_membership import CustomerMembership
    from base.plugins.product.models.product import Product
except ImportError:
    CustomerOrder = None
    OrderItem = None
    OrderStatus = None
    PaymentStatus = None
    PaymentMethod = None
    Customer = None
    CustomerMembership = None
    Product = None


class OrderService:
    model = "order"
    @staticmethod
    async def generate_order_no() -> str:
        from base.plugins.sales.models.order import generate_order_no
        return generate_order_no()

    @staticmethod
    @atomic()
    async def create_order(
        customer_id: int,
        items: List[Dict[str, Any]],
        payment_method: str,
        client_ip: Optional[str] = None,
        device_info: Optional[dict] = None,
        remark: Optional[str] = None
    ) -> CustomerOrder:
        customer = await Customer.get_or_none(id=customer_id)
        if not customer:
            raise ValueError("客户不存在")

        total_amount = Decimal("0.00")
        total_discount = Decimal("0.00")

        customer_membership = await CustomerMembership.get_or_none(
            customer_id=customer_id
        ).prefetch_related("membership_level")

        if customer_membership and customer_membership.membership_level:
            discount_percent = customer_membership.membership_level.discount_percentage or 0
        else:
            discount_percent = 0

        for item_data in items:
            quantity = item_data.get("quantity", 1)
            original_price = Decimal(str(item_data.get("unit_price", 0)))

            if discount_percent > 0:
                discount_amount = original_price * Decimal(discount_percent) / Decimal(100)
                discounted_price = original_price - discount_amount
            else:
                discounted_price = original_price

            item_total = discounted_price * quantity
            total_amount += item_total

            if discount_percent > 0:
                total_discount += (original_price - discounted_price) * quantity

        order_no = await OrderService.generate_order_no()
        expire_time = datetime.now(timezone.utc) + timedelta(minutes=30)

        try:
            payment_method_enum = PaymentMethod(payment_method)
        except ValueError as e:
            raise ValueError(f"无效的支付方式: {payment_method}，支持的方式: wechat, alipay, balance")

        order = await CustomerOrder.create(
            order_no=order_no,
            customer_id=customer_id,
            total_amount=total_amount,
            discount_amount=total_discount,
            final_amount=total_amount,
            payment_method=payment_method_enum,
            payment_status=PaymentStatus.PENDING,
            order_status=OrderStatus.PENDING,
            expire_time=expire_time,
            client_ip=client_ip,
            device_info=device_info,
            remark=remark
        )

        for item_data in items:
            quantity = item_data.get("quantity", 1)
            unit_price = Decimal(str(item_data.get("unit_price", 0)))
            total_price = unit_price * quantity

            product_type = item_data.get("product_type")
            extra_info = item_data.get("extra_info")
            product_id = item_data.get("product_id")

            if product_type in ["hours", "membership"] and not extra_info and product_id:
                product = await Product.get_or_none(id=product_id)
                if product:
                    recharge_hours = product.recharge_hours or 0
                    bonus_hours = product.bonus_hours or 0
                    total_hours = recharge_hours + bonus_hours

                    membership_level_id = product.membership_level_id
                    if not membership_level_id:
                        product_name = product.name.lower()
                        from base.plugins.customer.models.membership import MembershipLevel
                        if "svip" in product_name or "svip" in product.category.lower():
                            svip_level = await MembershipLevel.filter(
                                level_type="svip"
                            ).first()
                            membership_level_id = svip_level.id if svip_level else 3
                        elif "vip" in product_name and "svip" not in product_name:
                            vip_level = await MembershipLevel.filter(
                                level_type="vip"
                            ).first()
                            membership_level_id = vip_level.id if vip_level else 2
                        else:
                            regular_level = await MembershipLevel.filter(
                                level_type="regular"
                            ).first()
                            membership_level_id = regular_level.id if regular_level else 1

                    extra_info = {
                        "membership_level_id": membership_level_id,
                        "hours": recharge_hours,
                        "bonus_hours": bonus_hours,
                        "total_hours": total_hours
                    }

            await OrderItem.create(
                order_id=order.id,
                product_id=product_id,
                product_name=item_data.get("product_name"),
                product_type=product_type,
                product_image=item_data.get("product_image"),
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                extra_info=extra_info
            )

        await order.fetch_related('items')
        return order

    @staticmethod
    @atomic()
    async def create_membership_order(
        customer_id: int,
        membership_level_id: int,
        payment_method: str,
        client_ip: Optional[str] = None,
        device_info: Optional[dict] = None
    ) -> CustomerOrder:
        from base.plugins.customer.models.membership import MembershipLevel

        level = await MembershipLevel.get_or_none(id=membership_level_id)
        if not level:
            raise ValueError("会员等级不存在")

        if not level.is_active:
            raise ValueError("该会员等级已停用")

        items = [{
            "product_id": None,
            "product_name": level.name,
            "product_type": "membership",
            "product_image": None,
            "quantity": 1,
            "unit_price": float(level.price),
            "extra_info": {
                "membership_level_id": level.id,
                "membership_level_name": level.name,
                "hours": level.duration_hours,
                "bonus_hours": level.bonus_hours,
                "total_hours": level.duration_hours + level.bonus_hours
            }
        }]

        return await OrderService.create_order(
            customer_id=customer_id,
            items=items,
            payment_method=payment_method,
            client_ip=client_ip,
            device_info=device_info
        )

    @staticmethod
    async def get_order_by_id(order_id: int) -> Optional[CustomerOrder]:
        order = await CustomerOrder.get_or_none(id=order_id).prefetch_related('customer', 'items')
        return order

    @staticmethod
    async def get_order_by_no(order_no: str) -> Optional[CustomerOrder]:
        order = await CustomerOrder.get_or_none(order_no=order_no).prefetch_related('customer', 'items')
        return order

    @staticmethod
    async def get_orders_by_customer(
        customer_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> List[CustomerOrder]:
        offset = (page - 1) * page_size
        return await CustomerOrder.filter(
            customer_id=customer_id
        ).prefetch_related('items').order_by("-created_at").offset(offset).limit(page_size)

    @staticmethod
    async def get_all_orders(page: int = 1, page_size: int = 20, order_status: Optional[str] = None, payment_status: Optional[str] = None) -> List[CustomerOrder]:
        offset = (page - 1) * page_size
        query = CustomerOrder.all().prefetch_related('customer', 'items').order_by("-created_at")
        
        if order_status:
            query = query.filter(order_status=order_status)
        if payment_status:
            query = query.filter(payment_status=payment_status)
        
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def update_order_status(order_id: int, status: str) -> bool:
        if not hasattr(OrderStatus, status.upper()):
            raise ValueError(f"无效的订单状态: {status}")

        result = await CustomerOrder.filter(id=order_id).update(payment_status=status)
        return result > 0

    @staticmethod
    async def update_payment_status(
        order_id: int,
        status: str,
        payment_method: Optional[str] = None,
        transaction_id: Optional[str] = None
    ) -> bool:
        try:
            payment_status_enum = PaymentStatus(status)
        except ValueError:
            raise ValueError(f"无效的支付状态: {status}")

        update_data = {"payment_status": payment_status_enum}

        if payment_status_enum == PaymentStatus.PAID:
            update_data["pay_time"] = datetime.now(timezone.utc)

        if transaction_id:
            update_data["trade_no"] = transaction_id

        result = await CustomerOrder.filter(id=order_id).update(**update_data)

        if payment_status_enum == PaymentStatus.PAID and event_bus:
            try:
                order = await CustomerOrder.get_or_none(id=order_id)
                if order:
                    await event_bus.publish(
                        "sales.paid",
                        order_id=order.id,
                        order_no=order.order_no,
                        customer_id=order.customer_id,
                        customer_name=str(order.customer) if order.customer else "",
                        total_amount=float(order.total_amount),
                        tax_amount=float(order.tax_amount) if hasattr(order, 'tax_amount') else 0,
                        created_by="system",
                    )
            except Exception as e:
                logger.error(f"发布销售支付事件失败: {e}")

        return result > 0

    @staticmethod
    async def update_order_status(order_id: int, status: str) -> bool:
        try:
            order_status_enum = OrderStatus(status)
        except ValueError:
            raise ValueError(f"无效的订单状态: {status}")

        result = await CustomerOrder.filter(id=order_id).update(order_status=order_status_enum)
        return result > 0

    @staticmethod
    async def cancel_order(order_no: str) -> bool:
        order = await CustomerOrder.get_or_none(order_no=order_no)
        if not order:
            return False

        if order.payment_status != PaymentStatus.PENDING:
            return False

        await CustomerOrder.filter(order_no=order_no).update(payment_status=PaymentStatus.EXPIRED, order_status=OrderStatus.CANCELLED)
        return True

    @staticmethod
    async def get_order_items(order_id: int) -> List[OrderItem]:
        return await OrderItem.filter(order_id=order_id)

    @staticmethod
    async def process_payment_callback(
        order_no: str,
        transaction_id: str,
        transaction_type: str,
        amount: float,
        notify_data: Dict[str, Any]
    ) -> bool:
        order = await OrderService.get_order_by_no(order_no)
        if not order:
            return False

        if order.payment_status == PaymentStatus.PAID:
            return True

        if float(order.final_amount) != amount:
            return False

        order.payment_status = PaymentStatus.PAID
        order.order_status = OrderStatus.PROCESSING
        order.trade_no = transaction_id
        order.pay_time = datetime.now(timezone.utc)
        await order.save()

        items = await OrderService.get_order_items(order.id)
        for item in items:
            if item.product_type == "membership" and item.extra_info:
                from base.plugins.customer.services.membership_service import MembershipService

                extra = item.extra_info
                await MembershipService.create_customer_membership(
                    customer_id=order.customer_id,
                    membership_level_id=extra.get("membership_level_id"),
                    hours=extra.get("total_hours")
                )

        if event_bus:
            try:
                await event_bus.publish(
                    "sales.paid",
                    order_id=order.id,
                    order_no=order.order_no,
                    customer_id=order.customer_id,
                    customer_name=str(order.customer) if order.customer else "",
                    total_amount=float(order.total_amount),
                    tax_amount=float(order.tax_amount) if hasattr(order, 'tax_amount') else 0,
                    created_by="system",
                )
            except Exception as e:
                logger.error(f"发布销售支付事件失败: {e}")

        return True

    @staticmethod
    async def cancel_expired_orders() -> int:
        now = datetime.now(timezone.utc)

        expired_orders = await CustomerOrder.filter(
            payment_status=PaymentStatus.PENDING,
            expire_time__lt=now
        )

        cancelled_count = 0
        for order in expired_orders:
            try:
                order.payment_status = PaymentStatus.EXPIRED
                order.order_status = OrderStatus.CANCELLED
                await order.save()
                cancelled_count += 1
                print(f"[OrderService] 订单 {order.order_no} 已过期，自动取消")
            except Exception as e:
                print(f"[OrderService] 取消订单 {order.order_no} 失败: {e}")

        if cancelled_count > 0:
            print(f"[OrderService] 定时任务执行完成，取消 {cancelled_count} 个过期订单")

        return cancelled_count

    @staticmethod
    async def check_and_cancel_expired_order(order_no: str) -> bool:
        order = await OrderService.get_order_by_no(order_no)
        if not order:
            return False

        if order.payment_status != PaymentStatus.PENDING:
            return False

        now = datetime.now(timezone.utc)

        expire_time = order.expire_time
        if expire_time.tzinfo is not None:
            expire_time_utc = expire_time.astimezone(timezone.utc)
        else:
            expire_time_utc = expire_time.replace(tzinfo=timezone.utc)

        if now > expire_time_utc:
            order.payment_status = PaymentStatus.EXPIRED
            order.order_status = OrderStatus.CANCELLED
            await order.save()
            print(f"[OrderService] 订单 {order.order_no} 已过期，自动取消")
            return True

        return False
