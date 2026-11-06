from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from loguru import logger

from base.plugins.subcontracting.models.subcontracting_order import SubcontractingOrder
from base.plugins.subcontracting.models.supplier_material_price import SupplierMaterialPrice
from base.common.events.event_bus import event_bus
STATUS_LABELS = {
    "draft": "新建",
    "released": "已下发",
    "issuing": "发料中",
    "processing": "加工中",
    "partial_received": "部分收货",
    "completed": "已完成",
    "closed": "已关闭",
    "canceled": "已取消",
}


class SubcontractingOrderService:
    model = "subcontracting_order"

    @staticmethod
    async def get_by_id(order_id: int) -> Optional[SubcontractingOrder]:
        return await SubcontractingOrder.filter(id=order_id).first()

    @staticmethod
    async def get_by_code(sc_code: str) -> Optional[SubcontractingOrder]:
        return await SubcontractingOrder.filter(sc_code=sc_code).first()

    @staticmethod
    async def get_list(page: int = 1, page_size: int = 10, status: str = None,
                       supplier_code: str = None, product_code: str = None) -> Dict[str, Any]:
        query = SubcontractingOrder.all()
        if status:
            query = query.filter(status=status)
        if supplier_code:
            query = query.filter(supplier_code=supplier_code)
        if product_code:
            query = query.filter(product_code=product_code)
        total = await query.count()
        orders = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)
        items = []
        for o in orders:
            d = await o.to_dict()
            d["status_label"] = STATUS_LABELS.get(o.status, o.status)
            items.append(d)
        return {"total": total, "items": items}

    @staticmethod
    async def create_order(data: Dict[str, Any]) -> SubcontractingOrder:
        from base.plugins.purchase.models.supplier import Supplier, SupplierStatus
        supplier = await Supplier.filter(supplier_code=data.get("supplier_code")).first()
        if not supplier:
            raise ValueError(f"供应商编码 {data.get('supplier_code')} 不存在")
        if supplier.status == SupplierStatus.INACTIVE:
            raise ValueError(f"供应商 {supplier.supplier_name} 已禁用")
        if not supplier.is_subcontracting_qualified:
            raise ValueError(f"供应商 {supplier.supplier_name} 不具备委外加工资质")

        from base.plugins.mes.models.base_data import Route, RouteProcess
        route = await Route.filter(product_code=data.get("product_code"), is_active=True).first()
        if not route:
            raise ValueError(f"产品 {data.get('product_code')} 未配置工艺路线，无法创建委外工单")

        if data.get("process_code"):
            rp = await RouteProcess.filter(
                route_code=route.route_code,
                process_code=data["process_code"],
                is_subcontracting=True
            ).first()
            if not rp:
                raise ValueError(f"工序 {data['process_code']} 不是委外工序")

        price_record = await SupplierMaterialPrice.filter(
            supplier_code=data.get("supplier_code"),
            material_code=data.get("product_code"),
            is_active=True,
        ).order_by("-effective_date").first()
        if price_record and not data.get("processing_unit_price"):
            data["processing_unit_price"] = float(price_record.processing_unit_price)

        now = datetime.now()
        sc_code = f"SCO{now.strftime('%Y%m%d%H%M%S')}"
        order = await SubcontractingOrder.create(
            sc_code=sc_code,
            product_code=data.get("product_code", ""),
            product_name=data.get("product_name", ""),
            plan_quantity=data.get("plan_quantity", 0),
            actual_quantity=data.get("actual_quantity", 0),
            supplier_code=data.get("supplier_code", ""),
            supplier_name=data.get("supplier_name", ""),
            process_code=data.get("process_code"),
            process_name=data.get("process_name"),
            processing_unit_price=data.get("processing_unit_price", 0),
            scrap_rate=data.get("scrap_rate", 0),
            status="draft",
            planned_start_date=data.get("planned_start_date"),
            planned_end_date=data.get("planned_end_date"),
            source_planned_order_code=data.get("source_planned_order_code"),
            source_mps_code=data.get("source_mps_code"),
            remark=data.get("remark"),
        )
        logger.info(f"委外工单创建成功: {sc_code}")
        return order

    @staticmethod
    async def update_order(order_id: int, data: Dict[str, Any]) -> Optional[SubcontractingOrder]:
        order = await SubcontractingOrderService.get_by_id(order_id)
        if not order:
            raise ValueError("委外工单不存在")
        if order.status != "draft":
            raise ValueError("仅新建状态的委外工单可修改")
        update_fields = {}
        for key in ["product_name", "plan_quantity", "supplier_name", "process_name",
                     "processing_unit_price", "scrap_rate", "planned_start_date",
                     "planned_end_date", "remark"]:
            if key in data and data[key] is not None:
                update_fields[key] = data[key]
        if update_fields:
            await SubcontractingOrder.filter(id=order_id).update(**update_fields)
            order = await SubcontractingOrderService.get_by_id(order_id)
        return order

    @staticmethod
    async def delete_order(order_id: int) -> bool:
        order = await SubcontractingOrderService.get_by_id(order_id)
        if not order:
            raise ValueError("委外工单不存在")
        if order.status != "draft":
            raise ValueError("仅新建状态的委外工单可删除")
        await SubcontractingOrder.filter(id=order_id).delete()
        return True

    @staticmethod
    async def release_order(order_id: int) -> Optional[SubcontractingOrder]:
        order = await SubcontractingOrderService.get_by_id(order_id)
        if not order:
            raise ValueError("委外工单不存在")
        if order.status != "draft":
            raise ValueError(f"仅新建状态的工单可下发，当前状态: {STATUS_LABELS.get(order.status, order.status)}")
        await SubcontractingOrder.filter(id=order_id).update(status="released")
        order = await SubcontractingOrderService.get_by_id(order_id)
        if event_bus:
            await event_bus.publish("subcontracting.order_released", sc_code=order.sc_code, order_id=order.id)
        logger.info(f"委外工单下发: {order.sc_code}")
        return order

    @staticmethod
    async def cancel_order(order_id: int) -> Optional[SubcontractingOrder]:
        order = await SubcontractingOrderService.get_by_id(order_id)
        if not order:
            raise ValueError("委外工单不存在")
        if order.status in ("closed", "canceled"):
            raise ValueError(f"工单状态为 {STATUS_LABELS.get(order.status)}，无法取消")
        await SubcontractingOrder.filter(id=order_id).update(status="canceled")
        order = await SubcontractingOrderService.get_by_id(order_id)
        if event_bus:
            await event_bus.publish("subcontracting.order_canceled", sc_code=order.sc_code, order_id=order.id)
        logger.info(f"委外工单取消: {order.sc_code}")
        return order

    @staticmethod
    async def update_status_on_issue(sc_code: str) -> None:
        order = await SubcontractingOrder.filter(sc_code=sc_code).first()
        if not order:
            return
        if order.status in ("released", "issuing"):
            new_status = "issuing"
            if not order.actual_start_date:
                await SubcontractingOrder.filter(sc_code=sc_code).update(
                    status=new_status, actual_start_date=datetime.now()
                )
            else:
                await SubcontractingOrder.filter(sc_code=sc_code).update(status=new_status)

    @staticmethod
    async def update_status_on_receipt(sc_code: str, received_qty: Decimal) -> None:
        order = await SubcontractingOrder.filter(sc_code=sc_code).first()
        if not order:
            return
        new_total = order.total_received_quantity + received_qty
        if new_total >= order.plan_quantity:
            await SubcontractingOrder.filter(sc_code=sc_code).update(
                total_received_quantity=new_total,
                status="completed",
                actual_end_date=datetime.now(),
            )
        else:
            await SubcontractingOrder.filter(sc_code=sc_code).update(
                total_received_quantity=new_total,
                status="partial_received",
            )

    @staticmethod
    async def update_total_issued_quantity(sc_code: str, issued_qty: Decimal) -> None:
        order = await SubcontractingOrder.filter(sc_code=sc_code).first()
        if not order:
            return
        new_total = order.total_issued_quantity + issued_qty
        await SubcontractingOrder.filter(sc_code=sc_code).update(total_issued_quantity=new_total)