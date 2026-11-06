from fastapi import APIRouter, Query
from typing import Optional
from base.plugins.subcontracting.schemas.subcontracting_schema import SubcontractingReceiptCreate
from base.plugins.subcontracting.services.subcontracting_receipt_service import SubcontractingReceiptService

subcontracting_receipt_router = APIRouter(prefix="/receipts", tags=["委外-收货管理"])


@subcontracting_receipt_router.post("/", summary="创建委外收货单")
async def create_receipt(data: SubcontractingReceiptCreate):
    try:
        receipt = await SubcontractingReceiptService.create_receipt(data.dict())
        result = await receipt.to_dict()
        from base.plugins.subcontracting.services.subcontracting_receipt_service import RECEIPT_STATUS_LABELS
        result["status_label"] = RECEIPT_STATUS_LABELS.get(receipt.status, receipt.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_receipt_router.get("/", summary="查询委外收货单列表")
async def get_receipt_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    sc_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    return await SubcontractingReceiptService.get_list(
        page=page, page_size=page_size, sc_code=sc_code, status=status
    )


@subcontracting_receipt_router.get("/{receipt_id}", summary="获取收货单详情")
async def get_receipt(receipt_id: int):
    receipt = await SubcontractingReceiptService.get_by_id(receipt_id)
    if not receipt:
        return {"error": "收货单不存在"}
    result = await receipt.to_dict()
    from base.plugins.subcontracting.services.subcontracting_receipt_service import RECEIPT_STATUS_LABELS, INSPECTION_LABELS
    result["status_label"] = RECEIPT_STATUS_LABELS.get(receipt.status, receipt.status)
    result["inspection_result_label"] = INSPECTION_LABELS.get(receipt.inspection_result, receipt.inspection_result or "")
    from base.plugins.subcontracting.models.subcontracting_receipt import SubcontractingReceiptLine
    lines = await SubcontractingReceiptLine.filter(receipt_id=receipt.id).all()
    result["lines"] = [await l.to_dict() for l in lines]
    return result


@subcontracting_receipt_router.put("/{receipt_id}/confirm", summary="确认收货")
async def confirm_receipt(receipt_id: int):
    try:
        receipt = await SubcontractingReceiptService.confirm_receipt(receipt_id)
        result = await receipt.to_dict()
        from base.plugins.subcontracting.services.subcontracting_receipt_service import RECEIPT_STATUS_LABELS
        result["status_label"] = RECEIPT_STATUS_LABELS.get(receipt.status, receipt.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_receipt_router.put("/{receipt_id}/cancel", summary="取消收货单")
async def cancel_receipt(receipt_id: int):
    try:
        receipt = await SubcontractingReceiptService.cancel_receipt(receipt_id)
        result = await receipt.to_dict()
        from base.plugins.subcontracting.services.subcontracting_receipt_service import RECEIPT_STATUS_LABELS
        result["status_label"] = RECEIPT_STATUS_LABELS.get(receipt.status, receipt.status)
        return result
    except ValueError as e:
        return {"error": str(e)}