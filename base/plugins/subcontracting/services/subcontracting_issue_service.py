from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from loguru import logger

from base.plugins.subcontracting.models.subcontracting_issue import SubcontractingIssue, SubcontractingIssueLine
from base.plugins.subcontracting.services.subcontracting_order_service import SubcontractingOrderService
from base.common.events.event_bus import event_bus
ISSUE_STATUS_LABELS = {
    "draft": "待确认",
    "confirmed": "已确认",
    "canceled": "已取消",
}


class SubcontractingIssueService:
    model = "subcontracting_issue"

    @staticmethod
    async def get_by_id(issue_id: int) -> Optional[SubcontractingIssue]:
        return await SubcontractingIssue.filter(id=issue_id).first()

    @staticmethod
    async def get_list(page: int = 1, page_size: int = 10, sc_code: str = None,
                       status: str = None) -> Dict[str, Any]:
        query = SubcontractingIssue.all()
        if sc_code:
            query = query.filter(sc_code=sc_code)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        issues = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)
        items = []
        for issue in issues:
            d = await issue.to_dict()
            d["status_label"] = ISSUE_STATUS_LABELS.get(issue.status, issue.status)
            lines = await SubcontractingIssueLine.filter(issue_id=issue.id).all()
            d["lines"] = [await l.to_dict() for l in lines]
            items.append(d)
        return {"total": total, "items": items}

    @staticmethod
    async def create_issue(data: Dict[str, Any]) -> SubcontractingIssue:
        order = await SubcontractingOrderService.get_by_code(data.get("sc_code", ""))
        if not order:
            raise ValueError(f"委外工单 {data.get('sc_code')} 不存在")
        if order.status not in ("released", "issuing"):
            raise ValueError(f"委外工单状态为 {order.status}，无法发料")

        now = datetime.now()
        issue_code = f"SCI{now.strftime('%Y%m%d%H%M%S')}"
        issue = await SubcontractingIssue.create(
            issue_code=issue_code,
            sc_code=data.get("sc_code", ""),
            issue_type=data.get("issue_type", "auto"),
            source_warehouse_code=data.get("source_warehouse_code", ""),
            source_location_code=data.get("source_location_code"),
            supplier_location_code=data.get("supplier_location_code"),
            status="draft",
            applicant=data.get("applicant"),
            remark=data.get("remark"),
        )

        lines_data = data.get("lines", [])
        for line in lines_data:
            await SubcontractingIssueLine.create(
                issue_id=issue.id,
                material_code=line.get("material_code", ""),
                material_name=line.get("material_name", ""),
                required_quantity=line.get("required_quantity", 0),
                actual_quantity=line.get("actual_quantity", 0),
                uom=line.get("uom", ""),
                bom_quantity=line.get("bom_quantity", 0),
                is_bom_material=line.get("is_bom_material", True),
            )

        logger.info(f"委外发料单创建成功: {issue_code}")
        return issue

    @staticmethod
    async def generate_bom_lines(issue_id: int) -> List[Dict[str, Any]]:
        issue = await SubcontractingIssueService.get_by_id(issue_id)
        if not issue:
            raise ValueError("发料单不存在")
        order = await SubcontractingOrderService.get_by_code(issue.sc_code)
        if not order:
            raise ValueError("关联委外工单不存在")

        from base.plugins.mes.models.base_data import Bom
        bom_items = await Bom.filter(product_code=order.product_code, is_active=True).all()
        if not bom_items:
            raise ValueError(f"产品 {order.product_code} 无BOM物料清单")

        created_lines = []
        for bom in bom_items:
            scrap_rate = float(order.scrap_rate) if order.scrap_rate else 0
            required_qty = float(order.plan_quantity) * float(bom.quantity) * (1 + scrap_rate)
            line = await SubcontractingIssueLine.create(
                issue_id=issue_id,
                material_code=bom.item_code,
                material_name=bom.item_name,
                required_quantity=Decimal(str(round(required_qty, 6))),
                actual_quantity=Decimal("0"),
                uom=bom.unit,
                bom_quantity=bom.quantity,
                is_bom_material=True,
            )
            created_lines.append(await line.to_dict())

        await SubcontractingIssue.filter(id=issue_id).update(issue_type="auto")
        logger.info(f"发料单 {issue.issue_code} 按BOM生成 {len(created_lines)} 条明细")
        return created_lines

    @staticmethod
    async def confirm_issue(issue_id: int, confirmer: str = None) -> Optional[SubcontractingIssue]:
        issue = await SubcontractingIssueService.get_by_id(issue_id)
        if not issue:
            raise ValueError("发料单不存在")
        if issue.status != "draft":
            raise ValueError(f"发料单状态为 {issue.status}，仅待确认状态可确认")

        order = await SubcontractingOrderService.get_by_code(issue.sc_code)
        if not order:
            raise ValueError("关联委外工单不存在")
        if order.status in ("canceled", "closed"):
            raise ValueError(f"委外工单状态为 {order.status}，无法发料")

        lines = await SubcontractingIssueLine.filter(issue_id=issue_id).all()
        if not lines:
            raise ValueError("发料单无明细行，无法确认")

        total_actual = Decimal("0")
        for line in lines:
            actual = line.actual_quantity if line.actual_quantity else Decimal("0")
            required = line.required_quantity if line.required_quantity else Decimal("0")
            if actual <= 0:
                raise ValueError(f"物料 {line.material_code} 实际发料数量必须大于0")
            if actual > required * Decimal("1.2"):
                logger.warning(f"物料 {line.material_code} 实际发料数量超过需求量的120%")
            total_actual += actual

        await SubcontractingIssue.filter(id=issue_id).update(
            status="confirmed",
            confirmer=confirmer,
            confirmed_at=datetime.now(),
        )

        await SubcontractingOrderService.update_total_issued_quantity(issue.sc_code, total_actual)
        await SubcontractingOrderService.update_status_on_issue(issue.sc_code)

        if event_bus:
            await event_bus.publish(
                "subcontracting.issue_confirmed",
                issue_code=issue.issue_code,
                sc_code=issue.sc_code,
                issue_id=issue.id,
            )
        logger.info(f"委外发料单确认: {issue.issue_code}")
        return await SubcontractingIssueService.get_by_id(issue_id)

    @staticmethod
    async def cancel_issue(issue_id: int) -> Optional[SubcontractingIssue]:
        issue = await SubcontractingIssueService.get_by_id(issue_id)
        if not issue:
            raise ValueError("发料单不存在")
        if issue.status != "draft":
            raise ValueError("仅待确认状态的发料单可取消")
        await SubcontractingIssue.filter(id=issue_id).update(status="canceled")
        logger.info(f"委外发料单取消: {issue.issue_code}")
        return await SubcontractingIssueService.get_by_id(issue_id)