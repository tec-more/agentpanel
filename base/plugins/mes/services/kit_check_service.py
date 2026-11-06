from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from loguru import logger

try:
    from base.plugins.mes.models.base_data import Bom
    from base.plugins.mes.models.production import ManufacturingOrder
    from base.plugins.inventory.models.inventory_models import StockQuant
    from base.plugins.purchase.models.purchase_models import PurchaseOrder
    BOM_AVAILABLE = True
    QUANT_AVAILABLE = True
    PO_AVAILABLE = True
except ImportError:
    Bom = None
    ManufacturingOrder = None
    StockQuant = None
    PurchaseOrder = None
    BOM_AVAILABLE = False
    QUANT_AVAILABLE = False
    PO_AVAILABLE = False


class KitCheckService:
    """齐套检查服务"""
    model = "kit_check"

    @staticmethod
    async def _get_flattened_bom(product_code: str, quantity: Decimal = Decimal('1'), 
                                 current_level: int = 1, max_level: int = 10) -> List[Dict[str, Any]]:
        """递归展开BOM，获取扁平的物料需求清单"""
        if not BOM_AVAILABLE or Bom is None:
            return []

        if current_level > max_level:
            return []

        boms = await Bom.filter(product_code=product_code, is_active=True).order_by('level').all()
        if not boms:
            return []

        items = []
        for bom in boms:
            item_qty = Decimal(str(bom.quantity)) * quantity * (Decimal('1') + Decimal(str(bom.scrap_rate)))

            child_boms = await Bom.filter(product_code=bom.item_code, is_active=True).exists()
            if child_boms:
                child_items = await KitCheckService._get_flattened_bom(
                    bom.item_code, item_qty, current_level + 1, max_level
                )
                items.extend(child_items)
            else:
                items.append({
                    "item_code": bom.item_code,
                    "item_name": bom.item_name,
                    "required_quantity": float(item_qty),
                    "unit": bom.unit,
                    "scrap_rate": float(bom.scrap_rate),
                    "level": bom.level,
                    "product_code": product_code,
                })

        merged_items = {}
        for item in items:
            key = item["item_code"]
            if key not in merged_items:
                merged_items[key] = item.copy()
            else:
                merged_items[key]["required_quantity"] += item["required_quantity"]

        return list(merged_items.values())

    @staticmethod
    async def _get_available_stock(item_code: str) -> Tuple[float, float, float]:
        """获取物料的可用库存（考虑预留）"""
        if not QUANT_AVAILABLE or StockQuant is None:
            return 0.0, 0.0, 0.0

        quants = await StockQuant.filter(product_code=item_code).all()
        total_qty = 0.0
        total_reserved = 0.0
        total_available = 0.0

        for quant in quants:
            qty = float(quant.quantity) if hasattr(quant.quantity, '__float__') else 0.0
            reserved = float(quant.reserved_quantity) if hasattr(quant.reserved_quantity, '__float__') else 0.0
            available = float(quant.available_quantity) if hasattr(quant.available_quantity, '__float__') else 0.0
            
            total_qty += qty
            total_reserved += reserved
            total_available += available

        return total_qty, total_reserved, total_available

    @staticmethod
    async def _get_on_order_quantity(item_code: str) -> float:
        """获取物料的在途采购数量"""
        if not PO_AVAILABLE or PurchaseOrder is None:
            return 0.0

        pos = await PurchaseOrder.filter(item_code=item_code, status='confirmed').all()
        total_on_order = 0.0
        for po in pos:
            qty = float(po.quantity) if hasattr(po.quantity, '__float__') else 0.0
            received_qty = float(po.received_quantity) if hasattr(po.received_quantity, '__float__') else 0.0
            total_on_order += (qty - received_qty)

        return total_on_order

    @staticmethod
    async def check_kit_by_bom(product_code: str, quantity: int = 1) -> Dict[str, Any]:
        """检查指定产品和数量的齐套情况"""
        result = {
            "product_code": product_code,
            "product_name": "",
            "required_quantity": quantity,
            "total_items": 0,
            "shortage_items": 0,
            "kit_rate": 0.0,
            "kit_status": "no_kit",
            "items": [],
            "shortage_list": [],
            "created_at": None,
            "updated_at": None,
        }

        bom_items = await KitCheckService._get_flattened_bom(product_code, Decimal(str(quantity)))
        if not bom_items:
            result["msg"] = "产品BOM未维护或已失效"
            return result

        first_bom = await Bom.filter(product_code=product_code, is_active=True).first()
        if first_bom:
            result["product_name"] = first_bom.product_name

        total_items = len(bom_items)
        shortage_items = 0
        shortage_list = []

        for item in bom_items:
            total_qty, total_reserved, total_available = await KitCheckService._get_available_stock(item["item_code"])
            on_order_qty = await KitCheckService._get_on_order_quantity(item["item_code"])
            
            net_available = total_available + on_order_qty
            shortage = max(0, item["required_quantity"] - net_available)

            item_result = {
                "item_code": item["item_code"],
                "item_name": item["item_name"],
                "required_quantity": item["required_quantity"],
                "unit": item["unit"],
                "scrap_rate": item["scrap_rate"],
                "total_stock": total_qty,
                "reserved_stock": total_reserved,
                "available_stock": total_available,
                "on_order_stock": on_order_qty,
                "net_available": net_available,
                "shortage": shortage,
                "is_shortage": shortage > 0,
            }

            result["items"].append(item_result)

            if shortage > 0:
                shortage_items += 1
                shortage_list.append({
                    "item_code": item["item_code"],
                    "item_name": item["item_name"],
                    "required_quantity": item["required_quantity"],
                    "available_quantity": net_available,
                    "shortage": shortage,
                    "unit": item["unit"],
                })

        result["total_items"] = total_items
        result["shortage_items"] = shortage_items
        result["shortage_list"] = shortage_list

        if total_items > 0:
            result["kit_rate"] = round(((total_items - shortage_items) / total_items) * 100, 2)

        if shortage_items == 0:
            result["kit_status"] = "full_kit"
        elif shortage_items < total_items:
            result["kit_status"] = "partial_kit"
        else:
            result["kit_status"] = "no_kit"

        return result

    @staticmethod
    async def check_kit_by_mo(mo_id: int) -> Dict[str, Any]:
        """检查制造订单齐套情况"""
        if not ManufacturingOrder:
            return {"error": "制造订单模块不可用"}

        mo = await ManufacturingOrder.filter(id=mo_id).first()
        if not mo:
            return {"error": f"制造订单ID {mo_id} 不存在"}

        result = await KitCheckService.check_kit_by_bom(mo.product_code, mo.quantity)
        result["mo_id"] = mo_id
        result["mo_code"] = mo.mo_code
        result["mo_status"] = mo.status

        return result

    @staticmethod
    async def get_shortage_list(mo_id: int) -> List[Dict[str, Any]]:
        """获取制造订单的缺料清单"""
        result = await KitCheckService.check_kit_by_mo(mo_id)
        if "error" in result:
            return []
        return result.get("shortage_list", [])

    @staticmethod
    async def get_kit_status_by_mo(mo_code: str) -> str:
        """获取制造订单齐套状态"""
        if not ManufacturingOrder:
            return "unknown"

        mo = await ManufacturingOrder.filter(mo_code=mo_code).first()
        if not mo:
            return "unknown"

        result = await KitCheckService.check_kit_by_mo(mo.id)
        return result.get("kit_status", "unknown")

    @staticmethod
    async def batch_check_kit(mo_ids: List[int]) -> List[Dict[str, Any]]:
        """批量检查多个制造订单的齐套情况"""
        results = []
        for mo_id in mo_ids:
            result = await KitCheckService.check_kit_by_mo(mo_id)
            results.append(result)
        return results