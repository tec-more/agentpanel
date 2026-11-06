from typing import Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
from loguru import logger
try:
    from base.common.events.event_bus import event_bus
except ImportError:
    event_bus = None

try:
    from base.plugins.mes.models.material_flow import (
        MaterialRequisition, MaterialRequisitionDetail,
        MaterialReturn, ProductionReceipt
    )
    from base.plugins.mes.models.production import ManufacturingOrder
    from base.plugins.mes.schemas.material_flow_schema import (
        MaterialRequisitionCreate, MaterialReturnCreate, ProductionReceiptCreate
    )
    try:
        from base.plugins.mes.models.base_data import Bom
        BOM_AVAILABLE = True
    except ImportError:
        Bom = None
        BOM_AVAILABLE = False
    try:
        from base.plugins.inventory.models.inventory_models import StockQuant
        QUANT_AVAILABLE = True
    except ImportError:
        StockQuant = None
        QUANT_AVAILABLE = False
except ImportError:
    MaterialRequisition = None
    MaterialRequisitionDetail = None
    MaterialReturn = None
    ProductionReceipt = None
    ManufacturingOrder = None
    Bom = None
    StockQuant = None
    BOM_AVAILABLE = False
    QUANT_AVAILABLE = False


class MaterialRequisitionService:
    model = "material_requisition"
    @staticmethod
    async def create_requisition(data: MaterialRequisitionCreate) -> MaterialRequisition:
        mo = await ManufacturingOrder.filter(mo_code=data.mo_code).first()
        if not mo:
            raise ValueError(f"制造单{data.mo_code}不存在")

        requisition_code = f"MR{datetime.now().strftime('%Y%m%d%H%M%S')}"
        requisition = await MaterialRequisition.create(
            requisition_code=requisition_code,
            mo_code=data.mo_code,
            requisition_type=data.requisition_type,
            warehouse_code=data.warehouse_code,
            location_code=data.location_code,
            applicant=data.applicant,
            remark=data.remark
        )

        for detail in data.details:
            await MaterialRequisitionDetail.create(
                requisition_id=requisition.id,
                material_code=detail.material_code,
                material_name=detail.material_name,
                required_quantity=detail.required_quantity,
                unit=detail.unit,
                process_code=detail.process_code,
                substitute_material_code=detail.substitute_material_code
            )

        return requisition

    @staticmethod
    async def auto_generate_from_bom(mo_code: str) -> MaterialRequisition:
        mo = await ManufacturingOrder.filter(mo_code=mo_code).first()
        if not mo:
            raise ValueError(f"制造单{mo_code}不存在")

        details_data = []
        if BOM_AVAILABLE and Bom is not None:
            boms = await Bom.filter(product_code=mo.product_code, is_active=True)
            for bom in boms:
                qty = bom.quantity * mo.quantity * (1 + bom.scrap_rate)
                details_data.append({
                    "material_code": bom.item_code,
                    "material_name": bom.item_name,
                    "required_quantity": qty,
                    "unit": bom.unit,
                })

        requisition_code = f"MR{datetime.now().strftime('%Y%m%d%H%M%S')}"
        requisition = await MaterialRequisition.create(
            requisition_code=requisition_code,
            mo_code=mo_code,
            requisition_type="auto",
            warehouse_code="WH001",
            location_code="LOC001",
            applicant="system"
        )

        for d in details_data:
            await MaterialRequisitionDetail.create(
                requisition_id=requisition.id,
                material_code=d["material_code"],
                material_name=d["material_name"],
                required_quantity=d["required_quantity"],
                unit=d["unit"]
            )

        return requisition

    @staticmethod
    async def confirm_requisition(requisition_id: int, skip_stock_check: bool = False) -> Optional[MaterialRequisition]:
        req = await MaterialRequisition.filter(id=requisition_id).first()
        if not req:
            return None
        if req.status != "draft":
            raise ValueError("只能确认草稿状态的领料单")

        if QUANT_AVAILABLE and StockQuant is not None and not skip_stock_check:
            details = await MaterialRequisitionDetail.filter(requisition_id=requisition_id)
            shortage_items = []
            for detail in details:
                quants = await StockQuant.filter(product_code=detail.material_code)
                total_available = 0.0
                for quant in quants:
                    available = float(quant.available_quantity) if hasattr(quant.available_quantity, '__float__') else 0.0
                    total_available += available

                required = float(detail.required_quantity) if hasattr(detail.required_quantity, '__float__') else 0.0
                if total_available < required:
                    shortage_items.append({
                        "material_code": detail.material_code,
                        "material_name": detail.material_name,
                        "required": required,
                        "available": total_available,
                        "shortage": required - total_available,
                        "unit": detail.unit,
                    })

            if shortage_items:
                shortage_info = "; ".join([f"{item['material_name']}({item['material_code']})可用{item['available']}{item['unit']}，需{item['required']}{item['unit']}" for item in shortage_items])
                raise ValueError(f"库存不足，无法确认领料单。{shortage_info}")

        req.status = "confirmed"
        await req.save()

        if event_bus:
            try:
                details = await MaterialRequisitionDetail.filter(requisition_id=requisition_id)
                items_data = []
                for d in details:
                    items_data.append({
                        "product_id": None,
                        "product_code": d.material_code,
                        "product_name": d.material_name,
                        "quantity": float(d.required_quantity),
                        "unit_cost": 0,
                    })
                await event_bus.publish(
                    "material.picked",
                    pick_id=req.id,
                    pick_no=req.requisition_code,
                    items=items_data,
                    created_by=req.applicant or "system",
                )
            except Exception as e:
                logger.error(f"发布领料事件失败: {e}")

        return req

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        mo_code: Optional[str] = None,
        status: Optional[str] = None,
        requisition_type: Optional[str] = None
    ) -> Tuple[List[MaterialRequisition], int]:
        query = MaterialRequisition.all()
        if mo_code:
            query = query.filter(mo_code=mo_code)
        if status:
            query = query.filter(status=status)
        if requisition_type:
            query = query.filter(requisition_type=requisition_type)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total


class MaterialReturnService:
    model = "material_return"
    @staticmethod
    async def create_return(data: MaterialReturnCreate) -> MaterialReturn:
        req = await MaterialRequisition.filter(requisition_code=data.requisition_code).first()
        if not req:
            raise ValueError(f"领料单{data.requisition_code}不存在")

        return_code = f"MRT{datetime.now().strftime('%Y%m%d%H%M%S')}"
        return await MaterialReturn.create(
            return_code=return_code,
            mo_code=data.mo_code,
            requisition_code=data.requisition_code,
            warehouse_code=data.warehouse_code,
            location_code=data.location_code,
            operator=data.operator,
            remark=data.remark
        )

    @staticmethod
    async def confirm_return(return_id: int) -> Optional[MaterialReturn]:
        ret = await MaterialReturn.filter(id=return_id).first()
        if not ret:
            return None
        if ret.status != "draft":
            raise ValueError("只能确认草稿状态的退料单")
        ret.status = "confirmed"
        await ret.save()
        return ret

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        mo_code: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[List[MaterialReturn], int]:
        query = MaterialReturn.all()
        if mo_code:
            query = query.filter(mo_code=mo_code)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total


class ProductionReceiptService:
    model = "production_receipt"
    @staticmethod
    async def create_receipt(data: ProductionReceiptCreate) -> ProductionReceipt:
        mo = await ManufacturingOrder.filter(mo_code=data.mo_code).first()
        if not mo:
            raise ValueError(f"制造单{data.mo_code}不存在")

        batch_no = f"{data.product_code}-{datetime.now().strftime('%Y%m%d')}-001"
        receipt_code = f"PR{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return await ProductionReceipt.create(
            receipt_code=receipt_code,
            mo_code=data.mo_code,
            product_code=data.product_code,
            product_name=data.product_name,
            batch_no=batch_no,
            quantity=data.quantity,
            unit=data.unit,
            warehouse_code=data.warehouse_code,
            location_code=data.location_code,
            inspection_result=data.inspection_result,
            remark=data.remark
        )

    @staticmethod
    async def auto_create_receipt(mo_code: str) -> Optional[ProductionReceipt]:
        mo = await ManufacturingOrder.filter(mo_code=mo_code).first()
        if not mo:
            return None

        work_orders = await WorkOrder.filter(mo_code=mo_code)
        all_completed = all(wo.status in ("completed", "closed") for wo in work_orders) if work_orders else False
        if not all_completed:
            return None

        batch_no = f"{mo.product_code}-{datetime.now().strftime('%Y%m%d')}-001"
        receipt_code = f"PR{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return await ProductionReceipt.create(
            receipt_code=receipt_code,
            mo_code=mo_code,
            product_code=mo.product_code,
            product_name=mo.product_name,
            batch_no=batch_no,
            quantity=mo.actual_quantity,
            unit="个",
            warehouse_code="WH001",
            location_code="LOC001",
            inspection_result="qualified"
        )

    @staticmethod
    async def confirm_receipt(receipt_id: int) -> Optional[ProductionReceipt]:
        receipt = await ProductionReceipt.filter(id=receipt_id).first()
        if not receipt:
            return None
        if receipt.status != "draft":
            raise ValueError("只能确认草稿状态的入库单")
        if receipt.inspection_result not in ("qualified", "concession"):
            raise ValueError("未经质检合格的产品不允许入库")
        receipt.status = "confirmed"
        await receipt.save()

        if event_bus:
            try:
                await event_bus.publish(
                    "production.receipt",
                    receipt_id=receipt.id,
                    receipt_no=receipt.receipt_code,
                    items=[{
                        "product_id": None,
                        "product_code": receipt.product_code,
                        "product_name": receipt.product_name,
                        "quantity": float(receipt.quantity),
                        "unit_cost": 0,
                    }],
                    created_by="system",
                )
            except Exception as e:
                logger.error(f"发布生产入库事件失败: {e}")

        return receipt

    @staticmethod
    async def get_list(
        page: int = 1, page_size: int = 10,
        mo_code: Optional[str] = None,
        status: Optional[str] = None
    ) -> Tuple[List[ProductionReceipt], int]:
        query = ProductionReceipt.all()
        if mo_code:
            query = query.filter(mo_code=mo_code)
        if status:
            query = query.filter(status=status)
        total = await query.count()
        offset = (page - 1) * page_size
        items = await query.offset(offset).limit(page_size).order_by('-created_at')
        return items, total