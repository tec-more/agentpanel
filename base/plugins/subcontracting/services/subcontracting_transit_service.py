from typing import Dict, Any, List
from decimal import Decimal
from loguru import logger

from base.plugins.subcontracting.models.subcontracting_issue import SubcontractingIssue, SubcontractingIssueLine
from base.plugins.subcontracting.models.subcontracting_receipt import SubcontractingReceipt, SubcontractingReceiptLine
class SubcontractingTransitService:
    model = "subcontracting_transit"

    @staticmethod
    async def get_transit_list(page: int = 1, page_size: int = 10,
                               material_code: str = None,
                               supplier_code: str = None) -> Dict[str, Any]:
        issued = {}
        confirmed_issues = await SubcontractingIssue.filter(status="confirmed").all()
        for issue in confirmed_issues:
            lines = await SubcontractingIssueLine.filter(issue_id=issue.id).all()
            for line in lines:
                key = (line.material_code, issue.sc_code)
                if key not in issued:
                    issued[key] = {
                        "material_code": line.material_code,
                        "material_name": line.material_name,
                        "sc_code": issue.sc_code,
                        "issued_qty": Decimal("0"),
                        "uom": line.uom,
                    }
                issued[key]["issued_qty"] += line.actual_quantity or Decimal("0")

        received = {}
        confirmed_receipts = await SubcontractingReceipt.filter(status="confirmed").all()
        for receipt in confirmed_receipts:
            order = await _get_order_by_sc_code(receipt.sc_code)
            lines = await SubcontractingReceiptLine.filter(receipt_id=receipt.id).all()
            for line in lines:
                if order:
                    from base.plugins.mes.models.base_data import Bom
                    bom_items = await Bom.filter(product_code=line.product_code, is_active=True).all()
                    for bom in bom_items:
                        key = (bom.item_code, receipt.sc_code)
                        consumed = line.qualified_quantity * bom.quantity
                        if key not in received:
                            received[key] = Decimal("0")
                        received[key] += consumed

        transit_list = []
        for key, data in issued.items():
            material_code, sc_code = key
            transit_qty = data["issued_qty"] - received.get(key, Decimal("0"))
            if transit_qty < 0:
                transit_qty = Decimal("0")
            order = await _get_order_by_sc_code(sc_code)
            supplier_code = order.supplier_code if order else ""
            supplier_name = order.supplier_name if order else ""

            if material_code and material_code != material_code:
                continue
            if supplier_code and supplier_code != supplier_code:
                continue

            transit_list.append({
                "material_code": material_code,
                "material_name": data["material_name"],
                "supplier_code": supplier_code,
                "supplier_name": supplier_name,
                "transit_quantity": float(transit_qty),
                "uom": data["uom"],
            })

        total = len(transit_list)
        start = (page - 1) * page_size
        items = transit_list[start:start + page_size]
        return {"total": total, "items": items}

    @staticmethod
    async def get_transit_by_material(material_code: str) -> List[Dict[str, Any]]:
        result = await SubcontractingTransitService.get_transit_list(
            page=1, page_size=10000, material_code=material_code
        )
        return result.get("items", [])


async def _get_order_by_sc_code(sc_code: str):
    from base.plugins.subcontracting.models.subcontracting_order import SubcontractingOrder
    return await SubcontractingOrder.filter(sc_code=sc_code).first()