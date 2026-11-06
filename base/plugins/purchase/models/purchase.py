from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from tortoise import fields
from base.common.model import BaseModel, TimestampMixin
import random
import string


class PurchaseOrderStatus(str, Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PARTIAL_RECEIVED = "partial_received"
    FULL_RECEIVED = "full_received"
    CANCELLED = "cancelled"

    @classmethod
    def get_label(cls, value: str) -> str:
        labels = {
            cls.DRAFT.value: "草稿",
            cls.CONFIRMED.value: "已确认",
            cls.PARTIAL_RECEIVED.value: "部分入库",
            cls.FULL_RECEIVED.value: "全部入库",
            cls.CANCELLED.value: "已取消",
        }
        return labels.get(value, value)

    @classmethod
    def get_color(cls, value: str) -> str:
        colors = {
            cls.DRAFT.value: "default",
            cls.CONFIRMED.value: "warning",
            cls.PARTIAL_RECEIVED.value: "info",
            cls.FULL_RECEIVED.value: "success",
            cls.CANCELLED.value: "danger",
        }
        return colors.get(value, "default")


def generate_purchase_no() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.digits, k=6))
    return f"PO{timestamp}{random_str}"


def generate_receipt_no() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.digits, k=6))
    return f"PR{timestamp}{random_str}"


class PurchaseOrder(BaseModel, TimestampMixin):
    verbose_name = "采购订单"
    order_no = fields.CharField(max_length=64, unique=True, description="采购单号")
    supplier = fields.ForeignKeyField(
        "models.Supplier",
        related_name="purchase_orders",
        on_delete=fields.CASCADE,
        description="供应商"
    )
    status = fields.CharEnumField(
        PurchaseOrderStatus,
        max_length=30,
        default=PurchaseOrderStatus.DRAFT,
        description="订单状态"
    )

    order_date = fields.DatetimeField(default=datetime.now, description="下单日期")
    expected_delivery_date = fields.DatetimeField(null=True, description="预计交货日期")
    actual_delivery_date = fields.DatetimeField(null=True, description="实际交货日期")

    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="订单总金额")
    tax_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="税额")
    paid_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="已付金额")

    currency = fields.CharField(max_length=10, default="CNY", description="货币类型")
    exchange_rate = fields.DecimalField(max_digits=8, decimal_places=4, default=1, description="汇率")

    warehouse_id = fields.IntField(null=True, description="入库仓库ID")
    warehouse_code = fields.CharField(max_length=100, null=True, description="入库仓库编码")

    remark = fields.TextField(null=True, description="备注")
    created_by = fields.CharField(max_length=50, null=True, description="创建人")

    class Meta:
        table = "purchase_orders"
        ordering = ["-created_at"]

    async def to_dict(self) -> Dict[str, Any]:
        await self.fetch_related('supplier')

        items = await self.items.all()
        items_list = [await item.to_dict() for item in items]

        total_qty = sum(item['quantity'] for item in items_list)
        received_qty = sum(item['received_quantity'] for item in items_list)

        return {
            "id": self.id,
            "order_no": self.order_no,
            "supplier_id": self.supplier_id,
            "supplier_code": self.supplier.supplier_code if self.supplier else None,
            "supplier_name": self.supplier.supplier_name if self.supplier else None,
            "status": self.status.value,
            "status_label": PurchaseOrderStatus.get_label(self.status.value),
            "status_color": PurchaseOrderStatus.get_color(self.status.value),
            "order_date": self.order_date.strftime("%Y-%m-%d %H:%M:%S") if self.order_date else None,
            "expected_delivery_date": self.expected_delivery_date.strftime("%Y-%m-%d %H:%M:%S") if self.expected_delivery_date else None,
            "actual_delivery_date": self.actual_delivery_date.strftime("%Y-%m-%d %H:%M:%S") if self.actual_delivery_date else None,
            "total_amount": float(self.total_amount),
            "tax_amount": float(self.tax_amount),
            "paid_amount": float(self.paid_amount),
            "currency": self.currency,
            "exchange_rate": float(self.exchange_rate),
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "remark": self.remark,
            "created_by": self.created_by,
            "total_quantity": total_qty,
            "received_quantity": received_qty,
            "items": items_list,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class PurchaseOrderItem(BaseModel, TimestampMixin):
    purchase_order = fields.ForeignKeyField(
        "models.PurchaseOrder",
        related_name="items",
        on_delete=fields.CASCADE,
        description="采购订单"
    )

    product_id = fields.IntField(null=True, description="产品ID")
    product_code = fields.CharField(max_length=100, null=True, description="产品编码")
    product_name = fields.CharField(max_length=255, description="产品名称")
    product_spec = fields.CharField(max_length=255, null=True, description="产品规格")
    product_unit = fields.CharField(max_length=20, default="件", description="计量单位")

    quantity = fields.IntField(default=0, description="采购数量")
    received_quantity = fields.IntField(default=0, description="已入库数量")

    unit_price = fields.DecimalField(max_digits=10, decimal_places=2, default=0, description="单价")
    total_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="总价")

    tax_rate = fields.DecimalField(max_digits=5, decimal_places=2, default=0, description="税率")
    tax_amount = fields.DecimalField(max_digits=10, decimal_places=2, default=0, description="税额")

    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "purchase_order_items"
        ordering = ["id"]

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "purchase_order_id": self.purchase_order_id,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "product_spec": self.product_spec,
            "product_unit": self.product_unit,
            "quantity": self.quantity,
            "received_quantity": self.received_quantity,
            "unit_price": float(self.unit_price),
            "total_price": float(self.total_price),
            "tax_rate": float(self.tax_rate),
            "tax_amount": float(self.tax_amount),
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class PurchaseReceipt(BaseModel, TimestampMixin):
    verbose_name = "采购入库单"
    receipt_no = fields.CharField(max_length=64, unique=True, description="入库单号")
    purchase_order = fields.ForeignKeyField(
        "models.PurchaseOrder",
        related_name="receipts",
        on_delete=fields.CASCADE,
        description="关联采购订单"
    )

    receipt_date = fields.DatetimeField(default=datetime.now, description="入库日期")
    warehouse_id = fields.IntField(null=True, description="入库仓库ID")
    warehouse_code = fields.CharField(max_length=100, null=True, description="入库仓库编码")
    location_id = fields.IntField(null=True, description="入库库位ID")
    location_code = fields.CharField(max_length=100, null=True, description="入库库位编码")

    total_amount = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="入库总金额")

    inspector = fields.CharField(max_length=50, null=True, description="检验人")
    is_qualified = fields.BooleanField(default=True, description="是否合格")
    quality_result = fields.TextField(null=True, description="质检结果")

    remark = fields.TextField(null=True, description="备注")
    created_by = fields.CharField(max_length=50, null=True, description="创建人")

    class Meta:
        table = "purchase_receipts"
        ordering = ["-created_at"]

    async def to_dict(self) -> Dict[str, Any]:
        await self.fetch_related('purchase_order')

        items = await self.items.all()
        items_list = [await item.to_dict() for item in items]

        return {
            "id": self.id,
            "receipt_no": self.receipt_no,
            "purchase_order_id": self.purchase_order_id,
            "purchase_order_no": self.purchase_order.order_no if self.purchase_order else None,
            "supplier_id": self.purchase_order.supplier_id if self.purchase_order else None,
            "supplier_name": self.purchase_order.supplier.supplier_name if self.purchase_order and self.purchase_order.supplier else None,
            "receipt_date": self.receipt_date.strftime("%Y-%m-%d %H:%M:%S") if self.receipt_date else None,
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "location_id": self.location_id,
            "location_code": self.location_code,
            "total_amount": float(self.total_amount),
            "inspector": self.inspector,
            "is_qualified": self.is_qualified,
            "quality_result": self.quality_result,
            "remark": self.remark,
            "created_by": self.created_by,
            "items": items_list,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }


class PurchaseReceiptItem(BaseModel, TimestampMixin):
    receipt = fields.ForeignKeyField(
        "models.PurchaseReceipt",
        related_name="items",
        on_delete=fields.CASCADE,
        description="采购入库单"
    )

    order_item = fields.ForeignKeyField(
        "models.PurchaseOrderItem",
        related_name="receipt_items",
        on_delete=fields.CASCADE,
        null=True,
        description="关联采购订单行"
    )

    product_id = fields.IntField(null=True, description="产品ID")
    product_code = fields.CharField(max_length=100, null=True, description="产品编码")
    product_name = fields.CharField(max_length=255, description="产品名称")
    product_spec = fields.CharField(max_length=255, null=True, description="产品规格")
    product_unit = fields.CharField(max_length=20, default="件", description="计量单位")

    quantity = fields.IntField(default=0, description="入库数量")
    unit_price = fields.DecimalField(max_digits=10, decimal_places=2, default=0, description="单价")
    total_price = fields.DecimalField(max_digits=12, decimal_places=2, default=0, description="总价")

    batch_no = fields.CharField(max_length=100, null=True, description="批次号")
    expire_date = fields.DatetimeField(null=True, description="有效期")

    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "purchase_receipt_items"
        ordering = ["id"]

    async def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "receipt_id": self.receipt_id,
            "order_item_id": self.order_item_id,
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "product_spec": self.product_spec,
            "product_unit": self.product_unit,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "total_price": float(self.total_price),
            "batch_no": self.batch_no,
            "expire_date": self.expire_date.strftime("%Y-%m-%d") if self.expire_date else None,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }