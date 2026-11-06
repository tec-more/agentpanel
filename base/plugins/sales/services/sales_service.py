from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from decimal import Decimal

try:
    from base.plugins.sales.models.order import CustomerOrder, OrderItem, OrderStatus, PaymentStatus
    from base.plugins.customer.models.customer import Customer
except ImportError:
    CustomerOrder = None
    OrderItem = None
    OrderStatus = None
    PaymentStatus = None
    Customer = None


class SalesService:
    model = "sales"
    @staticmethod
    async def get_sales_overview(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        filters = {"payment_status": PaymentStatus.PAID}

        if start_date:
            filters["created_at__gte"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
            filters["created_at__gte"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        if end_date:
            end_of_day = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            filters["created_at__lt"] = end_of_day.replace(tzinfo=timezone.utc)

        paid_orders = await CustomerOrder.filter(**filters)

        total_orders = await CustomerOrder.filter(**filters).count()
        total_amount = Decimal("0.00")
        total_items = 0

        for order in paid_orders:
            total_amount += order.final_amount
            items = await OrderItem.filter(order_id=order.id)
            for item in items:
                total_items += item.quantity

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_orders = await CustomerOrder.filter(
            payment_status=PaymentStatus.PAID,
            created_at__gte=today_start
        ).count()

        today_amount = Decimal("0.00")
        today_order_list = await CustomerOrder.filter(
            payment_status=PaymentStatus.PAID,
            created_at__gte=today_start
        )
        for order in today_order_list:
            today_amount += order.final_amount

        pending_orders = await CustomerOrder.filter(payment_status=PaymentStatus.PENDING).count()
        cancelled_orders = await CustomerOrder.filter(order_status=OrderStatus.CANCELLED).count()

        return {
            "total_orders": total_orders,
            "total_amount": float(total_amount),
            "total_items": total_items,
            "today_orders": today_orders,
            "today_amount": float(today_amount),
            "pending_orders": pending_orders,
            "cancelled_orders": cancelled_orders,
            "start_date": start_date,
            "end_date": end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        }

    @staticmethod
    async def get_daily_sales(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)

        current = start
        result = []

        while current < end:
            day_start = current
            day_end = current + timedelta(days=1)

            orders = await CustomerOrder.filter(
                payment_status=PaymentStatus.PAID,
                created_at__gte=day_start,
                created_at__lt=day_end
            )

            day_amount = Decimal("0.00")
            day_count = 0
            for order in orders:
                day_amount += order.final_amount
                day_count += 1

            result.append({
                "date": current.strftime("%Y-%m-%d"),
                "orders_count": day_count,
                "amount": float(day_amount)
            })

            current += timedelta(days=1)

        return result

    @staticmethod
    async def get_monthly_sales(year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        month_start = datetime(year, month, 1).replace(tzinfo=timezone.utc)
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1).replace(tzinfo=timezone.utc)
        else:
            next_month_start = datetime(year, month + 1, 1).replace(tzinfo=timezone.utc)

        orders = await CustomerOrder.filter(
            payment_status=PaymentStatus.PAID,
            created_at__gte=month_start,
            created_at__lt=next_month_start
        )

        total_amount = Decimal("0.00")
        total_count = 0
        daily_data = []

        current = month_start
        while current < next_month_start:
            day_start = current
            day_end = current + timedelta(days=1)

            day_orders = await CustomerOrder.filter(
                payment_status=PaymentStatus.PAID,
                created_at__gte=day_start,
                created_at__lt=day_end
            )

            day_amount = Decimal("0.00")
            day_count = 0
            for order in day_orders:
                day_amount += order.final_amount
                day_count += 1

            total_amount += day_amount
            total_count += day_count

            daily_data.append({
                "date": current.strftime("%Y-%m-%d"),
                "day": current.day,
                "orders_count": day_count,
                "amount": float(day_amount)
            })

            current += timedelta(days=1)

        return {
            "year": year,
            "month": month,
            "total_amount": float(total_amount),
            "total_orders": total_count,
            "daily_data": daily_data
        }

    @staticmethod
    async def get_top_products(limit: int = 10, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = {"order__payment_status": PaymentStatus.PAID}

        if start_date:
            filters["order__created_at__gte"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            filters["order__created_at__gte"] = datetime.now(timezone.utc) - timedelta(days=30)

        if end_date:
            end_of_day = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            filters["order__created_at__lt"] = end_of_day.replace(tzinfo=timezone.utc)

        items = await OrderItem.filter(**filters).prefetch_related("order")

        product_map = {}
        for item in items:
            key = (item.product_name or "未知", item.product_type or "未知")
            if key not in product_map:
                product_map[key] = {
                    "total_sales": Decimal("0.00"),
                    "total_quantity": 0,
                    "order_ids": set()
                }
            product_map[key]["total_sales"] += item.total_price if item.total_price else Decimal("0.00")
            product_map[key]["total_quantity"] += item.quantity or 0
            product_map[key]["order_ids"].add(item.order_id)

        result = []
        for (product_name, product_type), stats in product_map.items():
            result.append({
                "product_name": product_name,
                "product_type": product_type,
                "total_sales": float(stats["total_sales"]),
                "total_quantity": stats["total_quantity"],
                "order_count": len(stats["order_ids"])
            })

        result.sort(key=lambda x: x["total_sales"], reverse=True)
        return result[:limit]

    @staticmethod
    async def get_top_customers(limit: int = 10, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        filters = {"payment_status": PaymentStatus.PAID}

        if start_date:
            filters["created_at__gte"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            filters["created_at__gte"] = datetime.now(timezone.utc) - timedelta(days=30)

        if end_date:
            end_of_day = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            filters["created_at__lt"] = end_of_day.replace(tzinfo=timezone.utc)

        orders = await CustomerOrder.filter(**filters).prefetch_related("customer")

        customer_map = {}
        for order in orders:
            customer_id = order.customer_id
            if customer_id not in customer_map:
                customer_map[customer_id] = {
                    "total_spent": Decimal("0.00"),
                    "order_count": 0,
                    "customer": order.customer
                }
            customer_map[customer_id]["total_spent"] += order.final_amount if order.final_amount else Decimal("0.00")
            customer_map[customer_id]["order_count"] += 1

        result = []
        for customer_id, stats in customer_map.items():
            customer = stats["customer"]
            customer_name = str(customer) if customer else "未知客户"
            customer_phone = customer.phone if customer else None
            result.append({
                "customer_id": customer_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "total_spent": float(stats["total_spent"]),
                "order_count": stats["order_count"]
            })

        result.sort(key=lambda x: x["total_spent"], reverse=True)
        return result[:limit]

    @staticmethod
    async def get_payment_method_stats(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        filters = {"payment_status": PaymentStatus.PAID}

        if start_date:
            filters["created_at__gte"] = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            filters["created_at__gte"] = datetime.now(timezone.utc) - timedelta(days=30)

        if end_date:
            end_of_day = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            filters["created_at__lt"] = end_of_day.replace(tzinfo=timezone.utc)

        orders = await CustomerOrder.filter(**filters)

        result = {}
        total_amount = Decimal("0.00")
        total_count = 0

        for order in orders:
            method = order.payment_method.value if hasattr(order.payment_method, 'value') else order.payment_method
            if method not in result:
                result[method] = {
                    "amount": Decimal("0.00"),
                    "count": 0
                }
            result[method]["amount"] += order.final_amount if order.final_amount else Decimal("0.00")
            result[method]["count"] += 1
            total_amount += order.final_amount if order.final_amount else Decimal("0.00")
            total_count += 1

        for method in result:
            if total_amount > 0:
                result[method]["percentage"] = round((float(result[method]["amount"]) / float(total_amount)) * 100, 2)
            result[method]["amount"] = float(result[method]["amount"])

        return {
            "total_amount": float(total_amount),
            "total_orders": total_count,
            "methods": result
        }
