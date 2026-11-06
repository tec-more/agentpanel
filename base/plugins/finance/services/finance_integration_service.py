import time
import random
import string
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from decimal import Decimal
from tortoise.transactions import atomic
try:
    from base.plugins.finance.models.integration_account_mapping import IntegrationAccountMapping
    from base.plugins.finance.models.integration_log import IntegrationLog
    from base.plugins.finance.models.integration_config import IntegrationConfig
    from base.plugins.finance.models.journal import JournalEntry, JournalLine, JournalType, JournalStatus
    from base.plugins.finance.models.account import Account
    from base.plugins.finance.models.payable import Payable, PayableStatus, Payment, PaymentStatus, PayableSettlement
    from base.plugins.finance.models.receivable import Receivable, ReceivableStatus, Receipt, ReceiptStatus, ReceivableSettlement
    from base.plugins.finance.models.inventory_cost import InventoryCost, CostMethod
    from base.plugins.finance.services.journal_service import JournalService
    from base.plugins.finance.services.integration_account_mapping_service import IntegrationAccountMappingService
    from base.plugins.finance.services.integration_log_service import IntegrationLogService
    from base.plugins.finance.services.integration_config_service import IntegrationConfigService
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False


def _generate_no(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}{ts}{rand}"


class FinanceIntegrationService:
    model = "finance_integration"
    @staticmethod
    async def _get_account_id_by_code(code: str) -> Optional[int]:
        account = await Account.get_or_none(code=code)
        return account.id if account else None

    @staticmethod
    async def _create_journal_for_event(event_type: str, amount: Decimal, tax_amount: Decimal, reference: str, description: str, created_by: str = "system") -> Optional[JournalEntry]:
        mapping = await IntegrationAccountMappingService.get_mapping_by_event_type(event_type)
        if not mapping:
            return None
        debit_account_id = await FinanceIntegrationService._get_account_id_by_code(mapping.debit_account_code)
        credit_account_id = await FinanceIntegrationService._get_account_id_by_code(mapping.credit_account_code)
        if not debit_account_id or not credit_account_id:
            return None
        lines = [
            {"account_id": debit_account_id, "debit": float(amount), "credit": 0},
            {"account_id": credit_account_id, "debit": 0, "credit": float(amount)},
        ]
        if tax_amount and tax_amount > 0:
            tax_debit_id = await FinanceIntegrationService._get_account_id_by_code(mapping.debit_account_code)
            tax_credit_id = await FinanceIntegrationService._get_account_id_by_code(
                mapping.debit_account_code.replace("1", "1221") if mapping.debit_account_code.startswith("1") else "2221"
            )
            if tax_debit_id and tax_credit_id:
                lines.append({"account_id": tax_debit_id, "debit": float(tax_amount), "credit": 0})
                lines.append({"account_id": tax_credit_id, "debit": 0, "credit": float(tax_amount)})
        journal = await JournalService.create_journal({
            "journal_type": _get_journal_type(event_type),
            "reference": reference,
            "description": description,
            "created_by": created_by,
            "lines": lines,
        })
        return journal

    @staticmethod
    @atomic()
    async def on_purchase_confirmed(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            order_id = data.get("order_id")
            order_no = data.get("order_no", "")
            supplier_id = data.get("supplier_id")
            supplier_name = data.get("supplier_name", "")
            total_amount = Decimal(str(data.get("total_amount", 0)))
            tax_amount = Decimal(str(data.get("tax_amount", 0)))
            created_by = data.get("created_by", "system")
            payable = await Payable.create(
                payable_no=_generate_no("AP"),
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                amount=total_amount,
                paid_amount=Decimal("0"),
                remaining_amount=total_amount,
                due_date=data.get("due_date", date.today()),
                status=PayableStatus.DRAFT,
                source_type="purchase_order",
                source_id=order_id,
                description=f"采购订单 {order_no} 自动生成",
                created_by=created_by,
            )
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="purchase_confirmed",
                amount=total_amount,
                tax_amount=tax_amount,
                reference=order_no,
                description=f"采购订单 {order_no} 确认",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "purchase_confirmed",
                "source_type": "purchase_order",
                "source_id": order_id,
                "source_no": order_no,
                "result": "success",
                "payable_id": payable.id,
                "journal_id": journal.id if journal else None,
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "payable_id": payable.id, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "purchase_confirmed",
                "source_type": "purchase_order",
                "source_id": data.get("order_id"),
                "source_no": data.get("order_no", ""),
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data

    @staticmethod
    @atomic()
    async def on_purchase_received(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            receipt_id = data.get("receipt_id")
            receipt_no = data.get("receipt_no", "")
            order_id = data.get("order_id")
            items = data.get("items", [])
            created_by = data.get("created_by", "system")
            period = datetime.now().strftime("%Y-%m")
            cost_ids = []
            for item in items:
                product_id = item.get("product_id")
                product_code = item.get("product_code", "")
                product_name = item.get("product_name", "")
                quantity = Decimal(str(item.get("quantity", 0)))
                unit_price = Decimal(str(item.get("unit_price", 0)))
                total_cost = quantity * unit_price
                ic = await InventoryCost.create(
                    product_id=product_id,
                    product_code=product_code,
                    product_name=product_name,
                    quantity=quantity,
                    unit_cost=unit_price,
                    total_cost=total_cost,
                    cost_method=CostMethod.WEIGHTED_AVERAGE,
                    period=period,
                    source_type="purchase_receipt",
                    source_id=receipt_id,
                )
                cost_ids.append(ic.id)
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="purchase_received",
                amount=sum(Decimal(str(i.get("quantity", 0))) * Decimal(str(i.get("unit_price", 0))) for i in items),
                tax_amount=Decimal("0"),
                reference=receipt_no,
                description=f"采购入库 {receipt_no}",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "purchase_received",
                "source_type": "purchase_receipt",
                "source_id": receipt_id,
                "source_no": receipt_no,
                "result": "success",
                "journal_id": journal.id if journal else None,
                "inventory_cost_ids": cost_ids,
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "inventory_cost_ids": cost_ids, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "purchase_received",
                "source_type": "purchase_receipt",
                "source_id": data.get("receipt_id"),
                "source_no": data.get("receipt_no", ""),
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data

    @staticmethod
    @atomic()
    async def on_purchase_payment(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            payable_id = data.get("payable_id")
            amount = Decimal(str(data.get("amount", 0)))
            supplier_id = data.get("supplier_id")
            supplier_name = data.get("supplier_name", "")
            created_by = data.get("created_by", "system")
            payment = await Payment.create(
                payment_no=_generate_no("PAY"),
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                amount=amount,
                payment_date=date.today(),
                status=PaymentStatus.DRAFT,
                payment_method=data.get("payment_method", "bank_transfer"),
                description=data.get("description", "采购付款"),
                created_by=created_by,
            )
            if payable_id:
                payable = await Payable.get_or_none(id=payable_id)
                if payable:
                    new_paid = payable.paid_amount + amount
                    new_remaining = payable.remaining_amount - amount
                    new_status = PayableStatus.PAID if new_remaining <= 0 else PayableStatus.PARTIAL
                    await Payable.filter(id=payable_id).update(
                        paid_amount=new_paid,
                        remaining_amount=max(new_remaining, Decimal("0")),
                        status=new_status,
                    )
                    await PayableSettlement.create(
                        payable_id=payable_id,
                        payment_id=payment.id,
                        amount=amount,
                        settlement_date=date.today(),
                        created_by=created_by,
                    )
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="purchase_payment",
                amount=amount,
                tax_amount=Decimal("0"),
                reference=payment.payment_no,
                description=f"采购付款 {payment.payment_no}",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "purchase_payment",
                "source_type": "payment",
                "source_id": payment.id,
                "source_no": payment.payment_no,
                "result": "success",
                "payment_id": payment.id,
                "journal_id": journal.id if journal else None,
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "payment_id": payment.id, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "purchase_payment",
                "source_type": "payment",
                "source_id": None,
                "source_no": "",
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data

    @staticmethod
    @atomic()
    async def on_sales_paid(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            order_id = data.get("order_id")
            order_no = data.get("order_no", "")
            customer_id = data.get("customer_id")
            customer_name = data.get("customer_name", "")
            total_amount = Decimal(str(data.get("total_amount", 0)))
            tax_amount = Decimal(str(data.get("tax_amount", 0)))
            created_by = data.get("created_by", "system")
            receivable = await Receivable.create(
                receivable_no=_generate_no("AR"),
                customer_id=customer_id,
                customer_name=customer_name,
                amount=total_amount,
                paid_amount=Decimal("0"),
                remaining_amount=total_amount,
                due_date=data.get("due_date", date.today()),
                status=ReceivableStatus.DRAFT,
                source_type="sales_order",
                source_id=order_id,
                description=f"销售订单 {order_no} 自动生成",
                created_by=created_by,
            )
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="sales_paid",
                amount=total_amount,
                tax_amount=tax_amount,
                reference=order_no,
                description=f"销售订单 {order_no} 确认",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "sales_paid",
                "source_type": "sales_order",
                "source_id": order_id,
                "source_no": order_no,
                "result": "success",
                "receivable_id": receivable.id,
                "journal_id": journal.id if journal else None,
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "receivable_id": receivable.id, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "sales_paid",
                "source_type": "sales_order",
                "source_id": data.get("order_id"),
                "source_no": data.get("order_no", ""),
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data

    @staticmethod
    @atomic()
    async def on_sales_receipt(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            receivable_id = data.get("receivable_id")
            amount = Decimal(str(data.get("amount", 0)))
            customer_id = data.get("customer_id")
            customer_name = data.get("customer_name", "")
            created_by = data.get("created_by", "system")
            receipt = await Receipt.create(
                receipt_no=_generate_no("RCV"),
                customer_id=customer_id,
                customer_name=customer_name,
                amount=amount,
                receipt_date=date.today(),
                status=ReceiptStatus.DRAFT,
                payment_method=data.get("payment_method", "bank_transfer"),
                description=data.get("description", "销售收款"),
                created_by=created_by,
            )
            if receivable_id:
                receivable = await Receivable.get_or_none(id=receivable_id)
                if receivable:
                    new_paid = receivable.paid_amount + amount
                    new_remaining = receivable.remaining_amount - amount
                    new_status = ReceivableStatus.PAID if new_remaining <= 0 else ReceivableStatus.PARTIAL
                    await Receivable.filter(id=receivable_id).update(
                        paid_amount=new_paid,
                        remaining_amount=max(new_remaining, Decimal("0")),
                        status=new_status,
                    )
                    await ReceivableSettlement.create(
                        receivable_id=receivable_id,
                        receipt_id=receipt.id,
                        amount=amount,
                        settlement_date=date.today(),
                        created_by=created_by,
                    )
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="sales_receipt",
                amount=amount,
                tax_amount=Decimal("0"),
                reference=receipt.receipt_no,
                description=f"销售收款 {receipt.receipt_no}",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "sales_receipt",
                "source_type": "receipt",
                "source_id": receipt.id,
                "source_no": receipt.receipt_no,
                "result": "success",
                "receipt_id": receipt.id,
                "journal_id": journal.id if journal else None,
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "receipt_id": receipt.id, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "sales_receipt",
                "source_type": "receipt",
                "source_id": None,
                "source_no": "",
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data

    @staticmethod
    @atomic()
    async def on_work_order_completed(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            wo_id = data.get("work_order_id")
            wo_no = data.get("work_order_no", "")
            product_code = data.get("product_code", "")
            product_name = data.get("product_name", "")
            completed_qty = Decimal(str(data.get("completed_quantity", 0)))
            unit_cost = Decimal(str(data.get("unit_cost", 0)))
            total_cost = completed_qty * unit_cost
            created_by = data.get("created_by", "system")
            period = datetime.now().strftime("%Y-%m")
            ic = await InventoryCost.create(
                product_id=data.get("product_id"),
                product_code=product_code,
                product_name=product_name,
                quantity=completed_qty,
                unit_cost=unit_cost,
                total_cost=total_cost,
                cost_method=CostMethod.WEIGHTED_AVERAGE,
                period=period,
                source_type="work_order",
                source_id=wo_id,
            )
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="work_order_completed",
                amount=total_cost,
                tax_amount=Decimal("0"),
                reference=wo_no,
                description=f"工单完工 {wo_no} 成本结转",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "work_order_completed",
                "source_type": "work_order",
                "source_id": wo_id,
                "source_no": wo_no,
                "result": "success",
                "journal_id": journal.id if journal else None,
                "inventory_cost_ids": [ic.id],
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "inventory_cost_id": ic.id, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "work_order_completed",
                "source_type": "work_order",
                "source_id": data.get("work_order_id"),
                "source_no": data.get("work_order_no", ""),
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data

    @staticmethod
    @atomic()
    async def on_material_picked(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            pick_id = data.get("pick_id")
            pick_no = data.get("pick_no", "")
            items = data.get("items", [])
            created_by = data.get("created_by", "system")
            period = datetime.now().strftime("%Y-%m")
            cost_ids = []
            total_amount = Decimal("0")
            for item in items:
                product_id = item.get("product_id")
                product_code = item.get("product_code", "")
                product_name = item.get("product_name", "")
                quantity = Decimal(str(item.get("quantity", 0)))
                unit_cost = Decimal(str(item.get("unit_cost", 0)))
                total_cost = quantity * unit_cost
                total_amount += total_cost
                ic = await InventoryCost.create(
                    product_id=product_id,
                    product_code=product_code,
                    product_name=product_name,
                    quantity=-quantity,
                    unit_cost=unit_cost,
                    total_cost=-total_cost,
                    cost_method=CostMethod.WEIGHTED_AVERAGE,
                    period=period,
                    source_type="material_pick",
                    source_id=pick_id,
                )
                cost_ids.append(ic.id)
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="material_picked",
                amount=total_amount,
                tax_amount=Decimal("0"),
                reference=pick_no,
                description=f"领料 {pick_no}",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "material_picked",
                "source_type": "material_pick",
                "source_id": pick_id,
                "source_no": pick_no,
                "result": "success",
                "journal_id": journal.id if journal else None,
                "inventory_cost_ids": cost_ids,
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "inventory_cost_ids": cost_ids, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "material_picked",
                "source_type": "material_pick",
                "source_id": data.get("pick_id"),
                "source_no": data.get("pick_no", ""),
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data

    @staticmethod
    @atomic()
    async def on_production_receipt(data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        result_data: Dict[str, Any] = {"result": "skipped"}
        if not FINANCE_AVAILABLE:
            return result_data
        try:
            receipt_id = data.get("receipt_id")
            receipt_no = data.get("receipt_no", "")
            items = data.get("items", [])
            created_by = data.get("created_by", "system")
            period = datetime.now().strftime("%Y-%m")
            cost_ids = []
            total_amount = Decimal("0")
            for item in items:
                product_id = item.get("product_id")
                product_code = item.get("product_code", "")
                product_name = item.get("product_name", "")
                quantity = Decimal(str(item.get("quantity", 0)))
                unit_cost = Decimal(str(item.get("unit_cost", 0)))
                total_cost = quantity * unit_cost
                total_amount += total_cost
                ic = await InventoryCost.create(
                    product_id=product_id,
                    product_code=product_code,
                    product_name=product_name,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    total_cost=total_cost,
                    cost_method=CostMethod.WEIGHTED_AVERAGE,
                    period=period,
                    source_type="production_receipt",
                    source_id=receipt_id,
                )
                cost_ids.append(ic.id)
            journal = await FinanceIntegrationService._create_journal_for_event(
                event_type="production_receipt",
                amount=total_amount,
                tax_amount=Decimal("0"),
                reference=receipt_no,
                description=f"生产入库 {receipt_no}",
                created_by=created_by,
            )
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "production_receipt",
                "source_type": "production_receipt",
                "source_id": receipt_id,
                "source_no": receipt_no,
                "result": "success",
                "journal_id": journal.id if journal else None,
                "inventory_cost_ids": cost_ids,
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "success", "inventory_cost_ids": cost_ids, "journal_id": journal.id if journal else None}
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            await IntegrationLogService.create_log({
                "event_name": "production_receipt",
                "source_type": "production_receipt",
                "source_id": data.get("receipt_id"),
                "source_no": data.get("receipt_no", ""),
                "result": "failed",
                "error_message": str(e),
                "processing_time_ms": elapsed,
            })
            result_data = {"result": "failed", "error": str(e)}
        return result_data


def _get_journal_type(event_type: str) -> str:
    mapping = {
        "purchase_confirmed": "purchase",
        "purchase_received": "purchase",
        "purchase_payment": "payment",
        "sales_paid": "sale",
        "sales_receipt": "receipt",
        "work_order_completed": "inventory",
        "material_picked": "inventory",
        "production_receipt": "inventory",
    }
    return mapping.get(event_type, "general")