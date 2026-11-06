from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from loguru import logger

from base.plugins.subcontracting.models.subcontracting_settlement import SubcontractingSettlement
from base.plugins.subcontracting.models.subcontracting_receipt import SubcontractingReceipt, SubcontractingReceiptLine
from base.plugins.subcontracting.services.subcontracting_order_service import SubcontractingOrderService
from base.common.events.event_bus import event_bus
SETTLEMENT_STATUS_LABELS = {
    "draft": "草稿",
    "submitted": "已提交",
    "approved": "已审核",
    "confirmed": "已确认",
}


class SubcontractingSettlementService:
    model = "subcontracting_settlement"

    @staticmethod
    async def get_by_id(settlement_id: int) -> Optional[SubcontractingSettlement]:
        return await SubcontractingSettlement.filter(id=settlement_id).first()

    @staticmethod
    async def get_list(page: int = 1, page_size: int = 10, sc_code: str = None,
                       supplier_code: str = None, status: str = None) -> Dict[str, Any]:
        query = SubcontractingSettlement.all()
        if sc_code:
            query = query.filter(sc_code=sc_code)
        if supplier_code:
            query = query.filter(supplier_code=supplier_code)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        settlements = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)
        items = []
        for s in settlements:
            d = await s.to_dict()
            d["status_label"] = SETTLEMENT_STATUS_LABELS.get(s.status, s.status)
            items.append(d)
        return {"total": total, "items": items}

    @staticmethod
    async def create_settlement(data: Dict[str, Any]) -> SubcontractingSettlement:
        order = await SubcontractingOrderService.get_by_code(data.get("sc_code", ""))
        if not order:
            raise ValueError(f"委外工单 {data.get('sc_code')} 不存在")

        confirmed_receipts = await SubcontractingReceipt.filter(
            sc_code=data.get("sc_code", ""), status="confirmed"
        ).all()
        if not confirmed_receipts:
            raise ValueError("委外工单尚无已确认的收货记录，无法结算")

        total_qualified = Decimal("0")
        total_concession = Decimal("0")
        for r in confirmed_receipts:
            lines = await SubcontractingReceiptLine.filter(receipt_id=r.id).all()
            for line in lines:
                total_qualified += line.qualified_quantity or Decimal("0")
                total_concession += line.concession_quantity or Decimal("0")

        unit_price = data.get("processing_unit_price")
        if unit_price is None:
            unit_price = float(order.processing_unit_price) if order.processing_unit_price else 0

        discount_rate = data.get("concession_discount_rate", 1)
        if discount_rate is None:
            discount_rate = 1

        settlement_amount = total_qualified * Decimal(str(unit_price)) + total_concession * Decimal(str(unit_price)) * Decimal(str(discount_rate))

        now = datetime.now()
        settlement_code = f"SCS{now.strftime('%Y%m%d%H%M%S')}"
        settlement = await SubcontractingSettlement.create(
            settlement_code=settlement_code,
            sc_code=data.get("sc_code", ""),
            supplier_code=data.get("supplier_code", order.supplier_code),
            period_start_date=data.get("period_start_date"),
            period_end_date=data.get("period_end_date"),
            qualified_quantity=total_qualified,
            concession_quantity=total_concession,
            processing_unit_price=unit_price,
            concession_discount_rate=discount_rate,
            settlement_amount=settlement_amount,
            currency=data.get("currency", "CNY"),
            status="draft",
            remark=data.get("remark"),
        )

        logger.info(f"委外结算单创建成功: {settlement_code}, 金额: {settlement_amount}")
        return settlement

    @staticmethod
    async def submit_settlement(settlement_id: int, submitter: str = None) -> Optional[SubcontractingSettlement]:
        settlement = await SubcontractingSettlementService.get_by_id(settlement_id)
        if not settlement:
            raise ValueError("结算单不存在")
        if settlement.status != "draft":
            raise ValueError(f"结算单状态为 {settlement.status}，仅草稿状态可提交")
        await SubcontractingSettlement.filter(id=settlement_id).update(
            status="submitted", submitter=submitter
        )
        logger.info(f"委外结算单提交: {settlement.settlement_code}")
        return await SubcontractingSettlementService.get_by_id(settlement_id)

    @staticmethod
    async def approve_settlement(settlement_id: int, approver: str = None) -> Optional[SubcontractingSettlement]:
        settlement = await SubcontractingSettlementService.get_by_id(settlement_id)
        if not settlement:
            raise ValueError("结算单不存在")
        if settlement.status != "submitted":
            raise ValueError(f"结算单状态为 {settlement.status}，仅已提交状态可审核")
        if settlement.submitter and approver and settlement.submitter == approver:
            raise ValueError("审核人不能与提交人相同")
        await SubcontractingSettlement.filter(id=settlement_id).update(
            status="approved", approver=approver
        )
        logger.info(f"委外结算单审核通过: {settlement.settlement_code}")
        return await SubcontractingSettlementService.get_by_id(settlement_id)

    @staticmethod
    async def confirm_settlement(settlement_id: int, confirmer: str = None) -> Optional[SubcontractingSettlement]:
        settlement = await SubcontractingSettlementService.get_by_id(settlement_id)
        if not settlement:
            raise ValueError("结算单不存在")
        if settlement.status != "approved":
            raise ValueError(f"结算单状态为 {settlement.status}，仅已审核状态可确认")

        await SubcontractingSettlement.filter(id=settlement_id).update(
            status="confirmed", confirmer=confirmer
        )

        try:
            from base.plugins.finance.models.payable import Payable, PayableStatus
            from base.plugins.purchase.models.supplier import Supplier
            supplier = await Supplier.filter(supplier_code=settlement.supplier_code).first()
            payable_no = f"AP-SC-{settlement.settlement_code}"
            existing = await Payable.filter(payable_no=payable_no).first()
            if not existing:
                await Payable.create(
                    payable_no=payable_no,
                    supplier=supplier,
                    supplier_name=settlement.supplier_code,
                    amount=float(settlement.settlement_amount),
                    paid_amount=0,
                    remaining_amount=float(settlement.settlement_amount),
                    due_date=datetime.now().date(),
                    status=PayableStatus.DRAFT,
                    source_type="subcontracting",
                    source_id=settlement.id,
                    description=f"委外结算单 {settlement.settlement_code} 应付",
                    created_by=confirmer or "system",
                )
                logger.info(f"委外结算推送应付凭证成功: {payable_no}")
        except Exception as e:
            logger.error(f"委外结算推送应付凭证失败: {e}", exc_info=True)

        if event_bus:
            await event_bus.publish(
                "subcontracting.settlement_confirmed",
                settlement_code=settlement.settlement_code,
                sc_code=settlement.sc_code,
                settlement_id=settlement.id,
                settlement_amount=float(settlement.settlement_amount),
            )
        logger.info(f"委外结算单确认: {settlement.settlement_code}")
        return await SubcontractingSettlementService.get_by_id(settlement_id)