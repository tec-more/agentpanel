from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from decimal import Decimal
from tortoise.exceptions import DoesNotExist
from loguru import logger

try:
    from base.common.events.event_bus import event_bus
except ImportError:
    event_bus = None

try:
    from base.plugins.purchase.models.supplier import Supplier, SupplierType, SupplierStatus
    from base.plugins.purchase.models.purchase import (
        PurchaseOrderStatus,
        PurchaseOrder,
        PurchaseOrderItem,
        PurchaseReceipt,
        PurchaseReceiptItem,
        generate_purchase_no,
        generate_receipt_no
    )
    from base.plugins.inventory.models.inventory_models import StockQuant, StockMoveLine, StockPicking, StockLocation
    from base.plugins.product.models.product import Product
except ImportError:
    Supplier = None
    SupplierType = None
    SupplierStatus = None
    PurchaseOrderStatus = None
    PurchaseOrder = None
    PurchaseOrderItem = None
    PurchaseReceipt = None
    PurchaseReceiptItem = None
    generate_purchase_no = None
    generate_receipt_no = None
    StockQuant = None
    StockMoveLine = None
    StockPicking = None
    StockLocation = None
    Product = None


class SupplierService:
    model = "supplier"

    @classmethod
    async def create(cls, data: Dict[str, Any]) -> Supplier:
        if not data.get('supplier_code'):
            max_code = await Supplier.all().order_by('-supplier_code').first()
            if max_code:
                num = int(max_code.supplier_code.replace('SUP', '')) + 1
            else:
                num = 1
            data['supplier_code'] = f"SUP{num:04d}"

        supplier = await Supplier.create(**data)
        return supplier

    @staticmethod
    async def get_supplier(supplier_id: int) -> Optional[Supplier]:
        try:
            return await Supplier.get(id=supplier_id)
        except DoesNotExist:
            return None

    @staticmethod
    async def get_supplier_by_code(supplier_code: str) -> Optional[Supplier]:
        try:
            return await Supplier.get(supplier_code=supplier_code)
        except DoesNotExist:
            return None

    @staticmethod
    async def get_supplier_list(
        page: int = 1,
        page_size: int = 10,
        supplier_name: str = None,
        supplier_type: str = None,
        status: str = None
    ) -> Dict[str, Any]:
        query = Supplier.all()

        if supplier_name:
            query = query.filter(supplier_name__icontains=supplier_name)
        if supplier_type:
            query = query.filter(supplier_type=supplier_type)
        if status:
            query = query.filter(status=status)

        total = await query.count()
        suppliers = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)

        return {
            "total": total,
            "items": [await s.to_dict() for s in suppliers]
        }

    @classmethod
    async def update(cls, supplier_id: int, data: Dict[str, Any]) -> Optional[Supplier]:
        supplier = await SupplierService.get_supplier(supplier_id)
        if not supplier:
            return None

        for key, value in data.items():
            if value is not None:
                setattr(supplier, key, value)

        await supplier.save()
        return supplier

    @classmethod
    async def delete(cls, supplier_id: int) -> bool:
        supplier = await SupplierService.get_supplier(supplier_id)
        if not supplier:
            return False

        await supplier.delete()
        return True

    @staticmethod
    async def get_active_suppliers() -> List[Supplier]:
        return await Supplier.filter(status=SupplierStatus.ACTIVE).order_by("supplier_name")


class PurchaseOrderService:
    model = "purchase_order"

    @classmethod
    async def create(cls, data: Dict[str, Any]) -> PurchaseOrder:
        items_data = data.pop('items', [])
        order_no = generate_purchase_no()

        order = await PurchaseOrder.create(order_no=order_no, **data)

        total_amount = Decimal("0.00")
        for item_data in items_data:
            item_data['purchase_order_id'] = order.id
            total_price = item_data['quantity'] * item_data.get('unit_price', Decimal("0"))
            item_data['total_price'] = total_price
            tax_amount = total_price * item_data.get('tax_rate', Decimal("0")) / Decimal("100")
            item_data['tax_amount'] = tax_amount
            await PurchaseOrderItem.create(**item_data)
            total_amount += total_price

        order.total_amount = total_amount
        await order.save()

        return order

    @staticmethod
    async def get_purchase_order(order_id: int) -> Optional[PurchaseOrder]:
        try:
            return await PurchaseOrder.get(id=order_id)
        except DoesNotExist:
            return None

    @staticmethod
    async def get_purchase_order_by_no(order_no: str) -> Optional[PurchaseOrder]:
        try:
            return await PurchaseOrder.get(order_no=order_no)
        except DoesNotExist:
            return None

    @staticmethod
    async def get_purchase_order_list(
        page: int = 1,
        page_size: int = 10,
        order_no: str = None,
        supplier_name: str = None,
        status: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        query = PurchaseOrder.all().prefetch_related('supplier')

        if order_no:
            query = query.filter(order_no__icontains=order_no)
        if supplier_name:
            query = query.filter(supplier__supplier_name__icontains=supplier_name)
        if status:
            query = query.filter(status=status)
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.filter(order_date__gte=start)
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(order_date__lt=end.replace(tzinfo=timezone.utc))

        total = await query.count()
        orders = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)

        return {
            "total": total,
            "items": [await o.to_dict() for o in orders]
        }

    @classmethod
    async def update(cls, order_id: int, data: Dict[str, Any]) -> Optional[PurchaseOrder]:
        order = await PurchaseOrderService.get_purchase_order(order_id)
        if not order:
            return None

        items_data = data.pop('items', None)

        for key, value in data.items():
            if value is not None:
                setattr(order, key, value)

        if items_data is not None:
            await PurchaseOrderItem.filter(purchase_order_id=order_id).delete()
            total_amount = Decimal("0.00")
            for item_data in items_data:
                item_data['purchase_order_id'] = order.id
                total_price = item_data['quantity'] * item_data.get('unit_price', Decimal("0"))
                item_data['total_price'] = total_price
                tax_amount = total_price * item_data.get('tax_rate', Decimal("0")) / Decimal("100")
                item_data['tax_amount'] = tax_amount
                await PurchaseOrderItem.create(**item_data)
                total_amount += total_price
            order.total_amount = total_amount

        await order.save()
        return order

    @staticmethod
    async def confirm_purchase_order(order_id: int) -> Optional[PurchaseOrder]:
        order = await PurchaseOrderService.get_purchase_order(order_id)
        if not order or order.status != PurchaseOrderStatus.DRAFT:
            return None

        order.status = PurchaseOrderStatus.CONFIRMED
        await order.save()

        if event_bus:
            try:
                await event_bus.publish(
                    "purchase.confirmed",
                    order_id=order.id,
                    order_no=order.order_no,
                    supplier_id=order.supplier_id,
                    supplier_name=(await order.supplier).supplier_name if order.supplier else "",
                    total_amount=float(order.total_amount),
                    tax_amount=float(order.tax_amount) if hasattr(order, 'tax_amount') else 0,
                    created_by=order.created_by or "system",
                )
            except Exception as e:
                logger.error(f"发布采购确认事件失败: {e}")

        return order

    @staticmethod
    async def cancel_purchase_order(order_id: int) -> Optional[PurchaseOrder]:
        order = await PurchaseOrderService.get_purchase_order(order_id)
        if not order or order.status == PurchaseOrderStatus.FULL_RECEIVED:
            return None

        order.status = PurchaseOrderStatus.CANCELLED
        await order.save()
        return order

    @classmethod
    async def delete(cls, order_id: int) -> bool:
        order = await PurchaseOrderService.get_purchase_order(order_id)
        if not order:
            return False

        await PurchaseOrderItem.filter(purchase_order_id=order_id).delete()
        await order.delete()
        return True

    @staticmethod
    async def update_order_status(order_id: int) -> PurchaseOrder:
        order = await PurchaseOrderService.get_purchase_order(order_id)
        if not order:
            return None

        items = await PurchaseOrderItem.filter(purchase_order_id=order_id)
        total_qty = sum(item.quantity for item in items)
        received_qty = sum(item.received_quantity for item in items)

        if received_qty == 0:
            order.status = PurchaseOrderStatus.CONFIRMED
        elif received_qty < total_qty:
            order.status = PurchaseOrderStatus.PARTIAL_RECEIVED
        else:
            order.status = PurchaseOrderStatus.FULL_RECEIVED
            order.actual_delivery_date = datetime.now()

        await order.save()
        return order


class PurchaseReceiptService:
    model = "purchase_receipt"

    @classmethod
    async def create(cls, data: Dict[str, Any]) -> PurchaseReceipt:
        items_data = data.pop('items', [])
        receipt_no = generate_receipt_no()

        purchase_order_id = data.get('purchase_order_id')
        order = await PurchaseOrderService.get_purchase_order(purchase_order_id)
        if not order:
            raise ValueError("采购订单不存在")

        receipt = await PurchaseReceipt.create(receipt_no=receipt_no, **data)

        total_amount = Decimal("0.00")
        for item_data in items_data:
            item_data['receipt_id'] = receipt.id

            if item_data.get('order_item_id'):
                order_item = await PurchaseOrderItem.get_or_none(id=item_data['order_item_id'])
                if order_item:
                    order_item.received_quantity += item_data['quantity']
                    await order_item.save()

            total_price = item_data['quantity'] * item_data.get('unit_price', Decimal("0"))
            item_data['total_price'] = total_price
            await PurchaseReceiptItem.create(**item_data)
            total_amount += total_price

        receipt.total_amount = total_amount
        await receipt.save()

        await PurchaseOrderService.update_order_status(purchase_order_id)

        await PurchaseReceiptService._create_inventory_stock_move(receipt)

        if event_bus:
            try:
                receipt_items = await receipt.items.all()
                items_data = []
                for ri in receipt_items:
                    items_data.append({
                        "product_id": ri.product_id,
                        "product_code": ri.product_code,
                        "product_name": ri.product_name,
                        "quantity": ri.quantity,
                        "unit_price": float(ri.unit_price),
                    })
                await event_bus.publish(
                    "purchase.received",
                    receipt_id=receipt.id,
                    receipt_no=receipt.receipt_no,
                    order_id=receipt.purchase_order_id,
                    items=items_data,
                    created_by=receipt.created_by or "system",
                )
            except Exception as e:
                logger.error(f"发布采购收货事件失败: {e}")

        return receipt

    @staticmethod
    async def _create_inventory_stock_move(receipt: PurchaseReceipt):
        if receipt.warehouse_id is None:
            return

        warehouse = await StockLocation.get_or_none(id=receipt.warehouse_id)
        if not warehouse:
            return

        supplier_location = await StockLocation.get_or_none(location_type='supplier')
        if not supplier_location:
            supplier_location = await StockLocation.create(
                location_code='SUP',
                location_name='供应商',
                location_type='supplier',
                usage='supplier'
            )

        picking = await StockPicking.create(
            picking_type='incoming',
            origin=receipt.receipt_no,
            state='done',
            location_id=supplier_location.id,
            location_dest_id=receipt.warehouse_id,
            location_code=supplier_location.location_code,
            location_dest_code=warehouse.location_code
        )

        items = await receipt.items.all()
        for item in items:
            move_line = await StockMoveLine.create(
                picking_id=picking.id,
                product_id=item.product_id,
                product_code=item.product_code or '',
                product_name=item.product_name,
                quantity=item.quantity,
                location_id=supplier_location.id,
                location_dest_id=receipt.location_id or receipt.warehouse_id,
                location_code=supplier_location.location_code,
                location_dest_code=receipt.location_code or warehouse.location_code
            )

            quant, _ = await StockQuant.get_or_create(
                product_id=item.product_id,
                location_id=receipt.location_id or receipt.warehouse_id,
                defaults={
                    'quantity': 0,
                    'product_code': item.product_code or '',
                    'product_name': item.product_name
                }
            )
            quant.quantity += item.quantity
            await quant.save()

    @staticmethod
    async def get_purchase_receipt(receipt_id: int) -> Optional[PurchaseReceipt]:
        try:
            return await PurchaseReceipt.get(id=receipt_id)
        except DoesNotExist:
            return None

    @staticmethod
    async def get_purchase_receipt_by_no(receipt_no: str) -> Optional[PurchaseReceipt]:
        try:
            return await PurchaseReceipt.get(receipt_no=receipt_no)
        except DoesNotExist:
            return None

    @staticmethod
    async def get_purchase_receipt_list(
        page: int = 1,
        page_size: int = 10,
        receipt_no: str = None,
        order_no: str = None,
        supplier_name: str = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        query = PurchaseReceipt.all().prefetch_related('purchase_order__supplier')

        if receipt_no:
            query = query.filter(receipt_no__icontains=receipt_no)
        if order_no:
            query = query.filter(purchase_order__order_no__icontains=order_no)
        if supplier_name:
            query = query.filter(purchase_order__supplier__supplier_name__icontains=supplier_name)
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.filter(receipt_date__gte=start)
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(receipt_date__lt=end.replace(tzinfo=timezone.utc))

        total = await query.count()
        receipts = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)

        return {
            "total": total,
            "items": [await r.to_dict() for r in receipts]
        }

    @classmethod
    async def update(cls, receipt_id: int, data: Dict[str, Any]) -> Optional[PurchaseReceipt]:
        receipt = await PurchaseReceiptService.get_purchase_receipt(receipt_id)
        if not receipt:
            return None

        items_data = data.pop('items', None)

        for key, value in data.items():
            if value is not None:
                setattr(receipt, key, value)

        if items_data is not None:
            await PurchaseReceiptItem.filter(receipt_id=receipt_id).delete()
            total_amount = Decimal("0.00")
            for item_data in items_data:
                item_data['receipt_id'] = receipt.id
                total_price = item_data['quantity'] * item_data.get('unit_price', Decimal("0"))
                item_data['total_price'] = total_price
                await PurchaseReceiptItem.create(**item_data)
                total_amount += total_price
            receipt.total_amount = total_amount

        await receipt.save()
        return receipt

    @classmethod
    async def delete(cls, receipt_id: int) -> bool:
        receipt = await PurchaseReceiptService.get_purchase_receipt(receipt_id)
        if not receipt:
            return False

        await PurchaseReceiptItem.filter(receipt_id=receipt_id).delete()
        await receipt.delete()
        return True