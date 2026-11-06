from fastapi import APIRouter, Depends, Query
from typing import Optional

from base.plugins.purchase.schemas import SupplierCreate, SupplierUpdate, SupplierResponse
from base.plugins.purchase.services import SupplierService

supplier_router = APIRouter(prefix="/supplier", tags=["采购-供应商管理"])


@supplier_router.post("/", response_model=SupplierResponse, summary="创建供应商")
async def create_supplier(data: SupplierCreate):
    supplier = await SupplierService.create(data.dict())
    return await supplier.to_dict()


@supplier_router.get("/{supplier_id}", response_model=SupplierResponse, summary="获取供应商详情")
async def get_supplier(supplier_id: int):
    supplier = await SupplierService.get_supplier(supplier_id)
    if not supplier:
        return {"error": "供应商不存在"}, 404
    return await supplier.to_dict()


@supplier_router.get("/", summary="获取供应商列表")
async def get_supplier_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    supplier_name: Optional[str] = Query(None),
    supplier_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    return await SupplierService.get_supplier_list(
        page=page,
        page_size=page_size,
        supplier_name=supplier_name,
        supplier_type=supplier_type,
        status=status
    )


@supplier_router.put("/{supplier_id}", response_model=SupplierResponse, summary="更新供应商")
async def update_supplier(supplier_id: int, data: SupplierUpdate):
    supplier = await SupplierService.update(supplier_id, data.dict())
    if not supplier:
        return {"error": "供应商不存在"}, 404
    return await supplier.to_dict()


@supplier_router.delete("/{supplier_id}", summary="删除供应商")
async def delete_supplier(supplier_id: int):
    success = await SupplierService.delete(supplier_id)
    if not success:
        return {"error": "供应商不存在"}, 404
    return {"message": "删除成功"}


@supplier_router.get("/active/list", summary="获取活跃供应商列表")
async def get_active_suppliers():
    suppliers = await SupplierService.get_active_suppliers()
    return [await s.to_dict() for s in suppliers]