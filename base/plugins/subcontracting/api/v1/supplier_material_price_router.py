from fastapi import APIRouter, Query
from typing import Optional
from decimal import Decimal
from base.plugins.subcontracting.models.supplier_material_price import SupplierMaterialPrice

supplier_material_price_router = APIRouter(prefix="/supplier-material-prices", tags=["委外-供应商物料加工单价"])


@supplier_material_price_router.post("/", summary="创建供应商物料加工单价")
async def create_price(
    supplier_code: str,
    material_code: str,
    material_name: str,
    processing_unit_price: Decimal = 0,
    currency: str = "CNY",
    effective_date: Optional[str] = None,
    expiry_date: Optional[str] = None,
    remark: Optional[str] = None,
):
    price = await SupplierMaterialPrice.create(
        supplier_code=supplier_code,
        material_code=material_code,
        material_name=material_name,
        processing_unit_price=processing_unit_price,
        currency=currency,
        effective_date=effective_date,
        expiry_date=expiry_date,
        remark=remark,
    )
    return await price.to_dict()


@supplier_material_price_router.get("/", summary="查询供应商物料加工单价列表")
async def get_price_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    supplier_code: Optional[str] = Query(None),
    material_code: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    query = SupplierMaterialPrice.all()
    if supplier_code:
        query = query.filter(supplier_code=supplier_code)
    if material_code:
        query = query.filter(material_code=material_code)
    if is_active is not None:
        query = query.filter(is_active=is_active)
    total = await query.count()
    items = await query.order_by("-created_at").offset((page - 1) * page_size).limit(page_size)
    return {"total": total, "items": [await p.to_dict() for p in items]}


@supplier_material_price_router.put("/{price_id}", summary="更新供应商物料加工单价")
async def update_price(price_id: int, processing_unit_price: Optional[Decimal] = None,
                       is_active: Optional[bool] = None, remark: Optional[str] = None):
    price = await SupplierMaterialPrice.filter(id=price_id).first()
    if not price:
        return {"error": "记录不存在"}
    update_fields = {}
    if processing_unit_price is not None:
        update_fields["processing_unit_price"] = processing_unit_price
    if is_active is not None:
        update_fields["is_active"] = is_active
    if remark is not None:
        update_fields["remark"] = remark
    if update_fields:
        await SupplierMaterialPrice.filter(id=price_id).update(**update_fields)
    price = await SupplierMaterialPrice.filter(id=price_id).first()
    return await price.to_dict()


@supplier_material_price_router.delete("/{price_id}", summary="删除供应商物料加工单价")
async def delete_price(price_id: int):
    price = await SupplierMaterialPrice.filter(id=price_id).first()
    if not price:
        return {"error": "记录不存在"}
    await SupplierMaterialPrice.filter(id=price_id).delete()
    return {"message": "删除成功"}