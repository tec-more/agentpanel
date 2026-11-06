from .order import (
    CustomerOrder,
    OrderItem,
    PaymentMethod,
    OrderStatus,
    generate_order_no
)

Order = CustomerOrder

__all__ = [
    'CustomerOrder',
    'Order',
    'OrderItem',
    'PaymentMethod',
    'OrderStatus',
    'generate_order_no',
]
