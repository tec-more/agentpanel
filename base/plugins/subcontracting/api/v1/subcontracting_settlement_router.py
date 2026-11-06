from fastapi import APIRouter, Query
from typing import Optional
from base.plugins.subcontracting.schemas.subcontracting_schema import SubcontractingSettlementCreate
from base.plugins.subcontracting.services.subcontracting_settlement_service import SubcontractingSettlementService

subcontracting_settlement_router = APIRouter(prefix="/settlements", tags=["委外-结算管理"])


@subcontracting_settlement_router.post("/", summary="创建委外结算单")
async def create_settlement(data: SubcontractingSettlementCreate):
    try:
        settlement = await SubcontractingSettlementService.create_settlement(data.dict())
        result = await settlement.to_dict()
        from base.plugins.subcontracting.services.subcontracting_settlement_service import SETTLEMENT_STATUS_LABELS
        result["status_label"] = SETTLEMENT_STATUS_LABELS.get(settlement.status, settlement.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_settlement_router.get("/", summary="查询委外结算单列表")
async def get_settlement_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    sc_code: Optional[str] = Query(None),
    supplier_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    return await SubcontractingSettlementService.get_list(
        page=page, page_size=page_size, sc_code=sc_code,
        supplier_code=supplier_code, status=status
    )


@subcontracting_settlement_router.get("/{settlement_id}", summary="获取结算单详情")
async def get_settlement(settlement_id: int):
    settlement = await SubcontractingSettlementService.get_by_id(settlement_id)
    if not settlement:
        return {"error": "结算单不存在"}
    result = await settlement.to_dict()
    from base.plugins.subcontracting.services.subcontracting_settlement_service import SETTLEMENT_STATUS_LABELS
    result["status_label"] = SETTLEMENT_STATUS_LABELS.get(settlement.status, settlement.status)
    return result


@subcontracting_settlement_router.put("/{settlement_id}/submit", summary="提交结算单")
async def submit_settlement(settlement_id: int, submitter: Optional[str] = None):
    try:
        settlement = await SubcontractingSettlementService.submit_settlement(settlement_id, submitter=submitter)
        result = await settlement.to_dict()
        from base.plugins.subcontracting.services.subcontracting_settlement_service import SETTLEMENT_STATUS_LABELS
        result["status_label"] = SETTLEMENT_STATUS_LABELS.get(settlement.status, settlement.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_settlement_router.put("/{settlement_id}/approve", summary="审核结算单")
async def approve_settlement(settlement_id: int, approver: Optional[str] = None):
    try:
        settlement = await SubcontractingSettlementService.approve_settlement(settlement_id, approver=approver)
        result = await settlement.to_dict()
        from base.plugins.subcontracting.services.subcontracting_settlement_service import SETTLEMENT_STATUS_LABELS
        result["status_label"] = SETTLEMENT_STATUS_LABELS.get(settlement.status, settlement.status)
        return result
    except ValueError as e:
        return {"error": str(e)}


@subcontracting_settlement_router.put("/{settlement_id}/confirm", summary="确认结算")
async def confirm_settlement(settlement_id: int, confirmer: Optional[str] = None):
    try:
        settlement = await SubcontractingSettlementService.confirm_settlement(settlement_id, confirmer=confirmer)
        result = await settlement.to_dict()
        from base.plugins.subcontracting.services.subcontracting_settlement_service import SETTLEMENT_STATUS_LABELS
        result["status_label"] = SETTLEMENT_STATUS_LABELS.get(settlement.status, settlement.status)
        return result
    except ValueError as e:
        return {"error": str(e)}