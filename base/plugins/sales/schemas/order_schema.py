from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field, computed_field
from decimal import Decimal


class OrderItemExtraInfo(BaseModel):
    membership_level_id: Optional[int] = Field(None, description="会员等级ID")
    membership_level_name: Optional[str] = Field(None, description="会员等级名称")
    hours: Optional[int] = Field(None, description="购买小时数")
    bonus_hours: Optional[int] = Field(None, description="赠送小时数")
    total_hours: Optional[int] = Field(None, description="总小时数")
    recharge_type: Optional[str] = Field(None, description="充值类型：monthly/yearly")


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., description="产品ID")
    product_name: str = Field(..., description="产品名称")
    product_type: str = Field(..., description="产品类型：membership/points/item")
    product_image: Optional[str] = Field(None, description="产品图片")
    quantity: int = Field(default=1, ge=1, le=100, description="购买数量")
    unit_price: Decimal = Field(..., gt=0, description="单价")
    extra_info: Optional[Dict[str, Any]] = Field(None, description="扩展信息")


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    product_id: Optional[int] = None
    product_name: str
    product_type: str
    product_image: Optional[str] = None
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    extra_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class CreateOrderIn(BaseModel):
    customer_id: int = Field(..., description="客户ID")
    items: List[OrderItemCreate] = Field(..., min_items=1, description="订单明细列表")
    payment_method: str = Field(..., description="支付方式(wechat/alipay/balance)")
    client_ip: Optional[str] = Field(None, description="客户端IP")
    device_info: Optional[Dict[str, Any]] = Field(None, description="设备信息")
    remark: Optional[str] = Field(None, description="备注")


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    customer_id: int
    customer_name: Optional[str] = None

    total_amount: Decimal
    discount_amount: Decimal
    final_amount: Decimal

    payment_method: str
    payment_status: str
    trade_no: Optional[str] = None
    pay_time: Optional[datetime] = None
    expire_time: datetime

    client_ip: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    remark: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    items: List[OrderItemOut] = []

    @computed_field
    @property
    def is_paid(self) -> bool:
        return self.payment_status == "paid"

    @computed_field
    @property
    def is_expired(self) -> bool:
        if self.pay_time:
            return False
        return datetime.now() > self.expire_time if self.expire_time else False

    @computed_field
    @property
    def status_color(self) -> str:
        colors = {
            "pending": "warning",
            "processing": "info",
            "paid": "success",
            "completed": "success",
            "cancelled": "default",
            "failed": "danger",
            "refunded": "secondary",
            "expired": "default",
        }
        return colors.get(self.payment_status, "default")

    @computed_field
    @property
    def status_label(self) -> str:
        labels = {
            "pending": "待支付",
            "processing": "处理中",
            "paid": "已支付",
            "completed": "已完成",
            "cancelled": "已取消",
            "failed": "支付失败",
            "refunded": "已退款",
            "expired": "已过期",
        }
        return labels.get(self.payment_status, "未知")

    @computed_field
    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items)


class OrderListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    customer_id: int
    customer_name: Optional[str] = None

    total_amount: Decimal
    final_amount: Decimal

    payment_method: str
    payment_status: str
    pay_time: Optional[datetime] = None
    expire_time: datetime

    created_at: datetime

    @computed_field
    @property
    def status_color(self) -> str:
        colors = {
            "pending": "warning",
            "processing": "info",
            "paid": "success",
            "completed": "success",
            "cancelled": "default",
            "failed": "danger",
            "refunded": "secondary",
            "expired": "default",
        }
        return colors.get(self.payment_status, "default")

    @computed_field
    @property
    def status_label(self) -> str:
        labels = {
            "pending": "待支付",
            "processing": "处理中",
            "paid": "已支付",
            "completed": "已完成",
            "cancelled": "已取消",
            "failed": "支付失败",
            "refunded": "已退款",
            "expired": "已过期",
        }
        return labels.get(self.payment_status, "未知")


class OrderListResponse(BaseModel):
    total: int
    items: List[OrderListOut]


class OrderCreateResponse(BaseModel):
    order_id: int
    order_no: str
    total_amount: Decimal
    final_amount: Decimal
    message: str = "订单创建成功"


class OrderUpdateRequest(BaseModel):
    payment_status: Optional[str] = Field(None, description="支付状态(pending/paid/failed/refunded/expired)")
    remark: Optional[str] = Field(None, description="订单备注")


class PaymentUpdateRequest(BaseModel):
    order_id: int = Field(..., description="订单ID")
    payment_status: str = Field(..., description="支付状态: pending/paid/failed/refunded")
    payment_method: Optional[str] = Field(None, description="支付方式")
    transaction_id: Optional[str] = Field(None, description="支付平台交易ID")


class PaymentWebhookIn(BaseModel):
    pass


class WechatPayNotifyIn(BaseModel):
    pass


class AlipayNotifyIn(BaseModel):
    pass


class OrderBase(BaseModel):
    customer_id: int = Field(..., description="客户ID")
    product_id: int = Field(..., description="产品ID")
    quantity: int = Field(default=1, ge=1, description="购买数量")
    remark: Optional[str] = Field(None, description="订单备注")


class OrderCreateRequest(OrderBase):
    pass


class OrderItemResponse(BaseModel):
    id: int
    order_no: str
    customer_id: int
    product_id: int
    product_name: Optional[str] = None
    product_type: str
    product_value: Optional[int] = None
    membership_duration: Optional[int] = None
    quantity: int
    unit_price: Decimal
    total_amount: Decimal
    payment_status: int
    order_status: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrderDetailResponse(OrderItemResponse):
    payment_method: Optional[str] = None
    payment_time: Optional[datetime] = None
    transaction_id: Optional[str] = None
    remark: Optional[str] = None
    updated_at: datetime
