from typing import Optional
from fastapi import APIRouter, HTTPException

from base.plugins.mes.services.material_flow_service import (
    MaterialRequisitionService, MaterialReturnService, ProductionReceiptService
)
from base.plugins.mes.schemas.material_flow_schema import (
    MaterialRequisitionCreate, MaterialReturnCreate, ProductionReceiptCreate
)
from base.common.response import success_response

material_requisition_router = APIRouter(prefix="/material-requisition", tags=["领料管理"])

@material_requisition_router.post("", summary="创建领料单")
async def create_requisition(data: MaterialRequisitionCreate):
    try:
        req = await MaterialRequisitionService.create_requisition(data)
        return success_response(data=req, msg="领料单创建成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@material_requisition_router.post("/auto-generate", summary="根据BOM自动生成领料单")
async def auto_generate_requisition(data: dict):
    mo_code = data.get("mo_code")
    if not mo_code:
        raise HTTPException(status_code=400, detail="制造单编码不能为空")
    try:
        req = await MaterialRequisitionService.auto_generate_from_bom(mo_code)
        return success_response(data=req, msg="领料单自动生成成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@material_requisition_router.post("/{requisition_id}/confirm", summary="确认领料单")
async def confirm_requisition(requisition_id: int):
    try:
        req = await MaterialRequisitionService.confirm_requisition(requisition_id)
        if not req:
            raise HTTPException(status_code=404, detail="领料单不存在")
        return success_response(data=req, msg="领料单已确认")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@material_requisition_router.get("", summary="获取领料单列表")
async def list_requisitions(
    page: int = 1, page_size: int = 10,
    mo_code: Optional[str] = None, status: Optional[str] = None
):
    items, total = await MaterialRequisitionService.get_list(
        page=page, page_size=page_size, mo_code=mo_code, status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


material_return_router = APIRouter(prefix="/material-return", tags=["退料管理"])

@material_return_router.post("", summary="创建退料单")
async def create_return(data: MaterialReturnCreate):
    try:
        ret = await MaterialReturnService.create_return(data)
        return success_response(data=ret, msg="退料单创建成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@material_return_router.post("/{return_id}/confirm", summary="确认退料单")
async def confirm_return(return_id: int):
    try:
        ret = await MaterialReturnService.confirm_return(return_id)
        if not ret:
            raise HTTPException(status_code=404, detail="退料单不存在")
        return success_response(data=ret, msg="退料单已确认")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@material_return_router.get("", summary="获取退料单列表")
async def list_returns(
    page: int = 1, page_size: int = 10,
    mo_code: Optional[str] = None, status: Optional[str] = None
):
    items, total = await MaterialReturnService.get_list(
        page=page, page_size=page_size, mo_code=mo_code, status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})


production_receipt_router = APIRouter(prefix="/production-receipt", tags=["完工入库"])

@production_receipt_router.post("", summary="创建入库单")
async def create_receipt(data: ProductionReceiptCreate):
    try:
        receipt = await ProductionReceiptService.create_receipt(data)
        return success_response(data=receipt, msg="入库单创建成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_receipt_router.post("/{receipt_id}/confirm", summary="确认入库单")
async def confirm_receipt(receipt_id: int):
    try:
        receipt = await ProductionReceiptService.confirm_receipt(receipt_id)
        if not receipt:
            raise HTTPException(status_code=404, detail="入库单不存在")
        return success_response(data=receipt, msg="入库单已确认")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@production_receipt_router.get("", summary="获取入库单列表")
async def list_receipts(
    page: int = 1, page_size: int = 10,
    mo_code: Optional[str] = None, status: Optional[str] = None
):
    items, total = await ProductionReceiptService.get_list(
        page=page, page_size=page_size, mo_code=mo_code, status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

material_flow_router = APIRouter()
material_flow_router.include_router(material_requisition_router)
material_flow_router.include_router(material_return_router)
material_flow_router.include_router(production_receipt_router)