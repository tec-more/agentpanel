from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
import random
import string


class PaymentMethod(str, Enum):
    WECHAT = "wechat"
    ALIPAY = "alipay"
    BALANCE = "balance"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @classmethod
    def get_status_color(cls, status: str) -> str:
        colors = {
            cls.PENDING.value: "warning",
            cls.PAID.value: "success",
            cls.FAILED.value: "danger",
            cls.REFUNDED.value: "secondary",
            cls.EXPIRED.value: "default",
            cls.CANCELLED.value: "danger",
        }
        return colors.get(status, "default")

    @classmethod
    def get_status_label(cls, status: str) -> str:
        labels = {
            cls.PENDING.value: "待支付",
            cls.PAID.value: "已支付",
            cls.FAILED.value: "支付失败",
            cls.REFUNDED.value: "已退款",
            cls.EXPIRED.value: "已过期",
            cls.CANCELLED.value: "已取消",
        }
        return labels.get(status, "未知")


class OrderStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @classmethod
    def get_status_color(cls, status: str) -> str:
        colors = {
            cls.DRAFT.value: "info",
            cls.PENDING.value: "warning",
            cls.PROCESSING.value: "primary",
            cls.SHIPPED.value: "primary",
            cls.COMPLETED.value: "success",
            cls.CANCELLED.value: "danger",
        }
        return colors.get(status, "default")

    @classmethod
    def get_status_label(cls, status: str) -> str:
        labels = {
            cls.DRAFT.value: "草稿",
            cls.PENDING.value: "待确认",
            cls.PROCESSING.value: "处理中",
            cls.SHIPPED.value: "已发货",
            cls.COMPLETED.value: "已完成",
            cls.CANCELLED.value: "已取消",
        }
        return labels.get(status, "未知")


def generate_order_no() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.digits, k=6))
    return f"ORD{timestamp}{random_str}"


class CustomerOrder(BaseModel, TimestampMixin):
    verbose_name = "客户订单"
    order_no = fields.CharField(max_length=64, unique=True, description="订单号")
    customer = fields.ForeignKeyField(
        "models.Customer",
        related_name="orders",
        on_delete=fields.CASCADE,
        description="客户"
    )

    total_amount = fields.DecimalField(max_digits=10, decimal_places=2, description="订单总金额")
    tax_amount = fields.DecimalField(max_digits=10, decimal_places=2, default=0, description="税额")
    discount_amount = fields.DecimalField(max_digits=10, decimal_places=2, default=0, description="优惠金额")
    final_amount = fields.DecimalField(max_digits=10, decimal_places=2, description="实际支付金额")

    payment_method = fields.CharEnumField(
        PaymentMethod,
        max_length=20,
        description="支付方式"
    )
    payment_status = fields.CharEnumField(
        PaymentStatus,
        max_length=20,
        default=PaymentStatus.PENDING,
        description="支付状态"
    )
    order_status = fields.CharEnumField(
        OrderStatus,
        max_length=20,
        default=OrderStatus.PENDING,
        description="订单状态"
    )
    trade_no = fields.CharField(max_length=128, null=True, description="第三方交易号")
    pay_time = fields.DatetimeField(null=True, description="支付时间")

    expire_time = fields.DatetimeField(description="订单过期时间")

    membership_level_id = fields.BigIntField(null=True, description="会员等级ID（旧字段，已弃用）")
    hours = fields.IntField(null=True, description="购买小时数（旧字段，已弃用）")
    bonus_hours = fields.IntField(null=True, description="赠送小时数（旧字段，已弃用）")
    total_hours = fields.IntField(null=True, description="总小时数（旧字段，已弃用）")
    amount = fields.DecimalField(max_digits=10, decimal_places=2, null=True, description="原金额字段（旧字段，已弃用）")

    client_ip = fields.CharField(max_length=50, null=True, description="客户端IP")
    device_info = fields.JSONField(null=True, description="设备信息")
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "orders"
        ordering = ["-created_at"]

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expire_time and self.payment_status == PaymentStatus.PENDING

    @property
    def is_paid(self) -> bool:
        return self.payment_status == PaymentStatus.PAID

    @property
    def payment_status_color(self) -> str:
        return PaymentStatus.get_status_color(self.payment_status.value)

    @property
    def payment_status_label(self) -> str:
        return PaymentStatus.get_status_label(self.payment_status.value)

    @property
    def order_status_color(self) -> str:
        return OrderStatus.get_status_color(self.order_status.value)

    @property
    def order_status_label(self) -> str:
        return OrderStatus.get_status_label(self.order_status.value)

    async def to_dict(self) -> Dict[str, Any]:
        await self.fetch_related('customer')

        items = await self.items.all()
        items_list = [await item.to_dict() for item in items]

        product_summary = []
        for item in items_list:
            product_summary.append(f"{item['product_name']} x{item['quantity']}")

        product_details = []
        for item in items_list:
            product_detail = {
                "product_name": item['product_name'],
                "product_type": item['product_type'],
                "quantity": item['quantity'],
                "unit_price": item['unit_price'],
                "total_price": item['total_price']
            }
            if item.get('product_id'):
                from base.plugins.product.models.product import Product
                product = await Product.get_or_none(id=item['product_id'])
                if product:
                    product_detail['product_description'] = product.description
                    if product.images and isinstance(product.images, list) and len(product.images) > 0:
                        product_detail['product_image'] = product.images[0]
                        product_detail['product_images'] = product.images
                    else:
                        product_detail['product_image'] = None
                        product_detail['product_images'] = []
            product_details.append(product_detail)

        data = {
            "id": self.id,
            "order_no": self.order_no,
            "customer_id": self.customer_id,
            "customer_name": str(self.customer) if self.customer else None,
            "total_amount": float(self.total_amount),
            "tax_amount": float(self.tax_amount),
            "discount_amount": float(self.discount_amount),
            "final_amount": float(self.final_amount),
            "payment_method": self.payment_method.value if isinstance(self.payment_method, Enum) else self.payment_method,
            "payment_status": self.payment_status.value if isinstance(self.payment_status, Enum) else self.payment_status,
            "order_status": self.order_status.value if isinstance(self.order_status, Enum) else self.order_status,
            "status": self.order_status.value if isinstance(self.order_status, Enum) else self.order_status,
            "trade_no": self.trade_no,
            "pay_time": self.pay_time.strftime("%Y-%m-%d %H:%M:%S") if self.pay_time else None,
            "expire_time": self.expire_time.strftime("%Y-%m-%d %H:%M:%S") if self.expire_time else None,
            "client_ip": self.client_ip,
            "device_info": self.device_info,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
            "items": items_list,
            "product_summary": product_summary,
            "product_details": product_details,
            "item_count": len(items_list),
            "first_product_name": items_list[0]['product_name'] if items_list else None,
            "first_product_image": items_list[0].get('product_image') if items_list else None,
        }
        return data

    def __str__(self):
        return f"Order {self.order_no} - {self.payment_status}"


class OrderItem(BaseModel, TimestampMixin):
    order = fields.ForeignKeyField(
        "models.CustomerOrder",
        related_name="items",
        on_delete=fields.CASCADE,
        description="订单"
    )
    product = fields.ForeignKeyField(
        "models.Product",
        related_name="order_items",
        on_delete=fields.SET_NULL,
        null=True,
        description="产品"
    )

    product_name = fields.CharField(max_length=255, description="产品名称")
    product_type = fields.CharField(max_length=50, description="产品类型：membership/points/item")
    product_image = fields.CharField(max_length=500, null=True, description="产品图片")

    quantity = fields.IntField(default=1, description="购买数量")
    unit_price = fields.DecimalField(max_digits=10, decimal_places=2, description="单价")
    total_price = fields.DecimalField(max_digits=10, decimal_places=2, description="小计金额")

    extra_info = fields.JSONField(null=True, description="扩展信息")

    class Meta:
        table = "order_items"
        ordering = ["-created_at"]

    async def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "order_id": self.order_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "product_type": self.product_type,
            "product_image": self.product_image,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total_price": float(self.total_price),
            "extra_info": self.extra_info,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        return data

    def __str__(self):
        return f"OrderItem {self.product_name} x {self.quantity}"
