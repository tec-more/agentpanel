from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from loguru import logger

from base.plugins.subcontracting.models.subcontracting_receipt import SubcontractingReceipt, SubcontractingReceiptLine
from base.plugins.subcontracting.services.subcontracting_order_service import SubcontractingOrderService
from base.common.events.event_bus import event_bus
RECEIPT_STATUS_LABELS = {
    "draft": "待确认",
    "confirmed": "已确认",
    "canceled": "已取消",
}

INSPECTION_LABELS = {
    "qualified": "合格",
    "unqualified": "不合格",
    "concession": "让步接收",
}


class SubcontractingReceiptService:
    model = "subcontracting_receipt"

    @staticmethod
    async def get_by_id(receipt_id: int) -> Optional[SubcontractingReceipt]:
        return await SubcontractingReceipt.filter(id=receipt_id).first()

    @staticmethod
    async def get_list(page: int = 1, page_size: int = 10, sc_code: str = None,
                       status: str = None) -> Dict[str, Any]:
        query = SubcontractingReceipt.all()
        if sc_code:
            query = query.filter(sc_code=sc_code)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        receipts = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)
        items = []
        for r in receipts:
            d = await r.to_dict()
            d["status_label"] = RECEIPT_STATUS_LABELS.get(r.status, r.status)
            d["inspection_result_label"] = INSPECTION_LABELS.get(r.inspection_result, r.inspection_result or "")
            lines = await SubcontractingReceiptLine.filter(receipt_id=r.id).all()
            d["lines"] = [await l.to_dict() for l in lines]
            items.append(d)
        return {"total": total, "items": items}

    @staticmethod
    async def create_receipt(data: Dict[str, Any]) -> SubcontractingReceipt:
        order = await SubcontractingOrderService.get_by_code(data.get("sc_code", ""))
        if not order:
            raise ValueError(f"委外工单 {data.get('sc_code')} 不存在")
        if order.status not in ("issuing", "processing", "partial_received"):
            raise ValueError(f"委外工单状态为 {order.status}，无法收货")

        now = datetime.now()
        receipt_code = f"SCR{now.strftime('%Y%m%d%H%M%S')}"
        receipt = await SubcontractingReceipt.create(
            receipt_code=receipt_code,
            sc_code=data.get("sc_code", ""),
            supplier_code=data.get("supplier_code", ""),
            receipt_warehouse_code=data.get("receipt_warehouse_code", ""),
            receipt_location_code=data.get("receipt_location_code"),
            inspection_result=data.get("inspection_result"),
            inspector=data.get("inspector"),
            status="draft",
            receiver=data.get("receiver"),
            remark=data.get("remark"),
        )

        lines_data = data.get("lines", [])
        for line in lines_data:
            await SubcontractingReceiptLine.create(
                receipt_id=receipt.id,
                product_code=line.get("product_code", ""),
                product_name=line.get("product_name", ""),
                receipt_quantity=line.get("receipt_quantity", 0),
                qualified_quantity=line.get("qualified_quantity", 0),
                unqualified_quantity=line.get("unqualified_quantity", 0),
                concession_quantity=line.get("concession_quantity", 0),
                uom=line.get("uom", ""),
                batch_no=line.get("batch_no"),
            )

        logger.info(f"委外收货单创建成功: {receipt_code}")
        return receipt

    @staticmethod
    async def confirm_receipt(receipt_id: int) -> Optional[SubcontractingReceipt]:
        receipt = await SubcontractingReceiptService.get_by_id(receipt_id)
        if not receipt:
            raise ValueError("收货单不存在")
        if receipt.status != "draft":
            raise ValueError(f"收货单状态为 {receipt.status}，仅待确认状态可确认")

        order = await SubcontractingOrderService.get_by_code(receipt.sc_code)
        if not order:
            raise ValueError("关联委外工单不存在")
        if order.status in ("canceled", "closed"):
            raise ValueError(f"委外工单状态为 {order.status}，无法收货")

        lines = await SubcontractingReceiptLine.filter(receipt_id=receipt_id).all()
        if not lines:
            raise ValueError("收货单无明细行，无法确认")

        total_qualified = Decimal("0")
        total_concession = Decimal("0")
        for line in lines:
            if line.product_code != order.product_code:
                raise ValueError(f"收货物料 {line.product_code} 与委外工单产品 {order.product_code} 不匹配")
            total_qualified += line.qualified_quantity or Decimal("0")
            total_concession += line.concession_quantity or Decimal("0")

        if total_qualified + total_concession <= 0:
            if receipt.inspection_result == "unqualified":
                await SubcontractingReceipt.filter(id=receipt_id).update(status="confirmed")
                logger.info(f"委外收货单确认(质检不合格，未入库): {receipt.receipt_code}")
                return await SubcontractingReceiptService.get_by_id(receipt_id)
            raise ValueError("收货数量必须大于0")

        if order.total_received_quantity + total_qualified + total_concession > order.plan_quantity:
            logger.warning(f"委外工单 {order.sc_code} 累计收货数量可能超过计划数量")

        await SubcontractingReceipt.filter(id=receipt_id).update(
            status="confirmed",
            confirmed_at=datetime.now(),
        )

        await SubcontractingOrderService.update_status_on_receipt(
            receipt.sc_code, total_qualified + total_concession
        )

        if event_bus:
            await event_bus.publish(
                "subcontracting.receipt_confirmed",
                receipt_code=receipt.receipt_code,
                sc_code=receipt.sc_code,
                receipt_id=receipt.id,
                qualified_quantity=float(total_qualified),
                concession_quantity=float(total_concession),
            )
        logger.info(f"委外收货单确认: {receipt.receipt_code}")
        return await SubcontractingReceiptService.get_by_id(receipt_id)

    @staticmethod
    async def cancel_receipt(receipt_id: int) -> Optional[SubcontractingReceipt]:
        receipt = await SubcontractingReceiptService.get_by_id(receipt_id)
        if not receipt:
            raise ValueError("收货单不存在")
        if receipt.status != "draft":
            raise ValueError("仅待确认状态的收货单可取消")
        await SubcontractingReceipt.filter(id=receipt_id).update(status="canceled")
        logger.info(f"委外收货单取消: {receipt.receipt_code}")
        return await SubcontractingReceiptService.get_by_id(receipt_id)