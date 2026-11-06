from typing import Optional
from fastapi import APIRouter, HTTPException

from base.plugins.mrp2.services.mrp_service import MRPService
from base.plugins.mrp2.services.planned_order_service import PlannedOrderService
from base.plugins.mrp2.schemas.mrp_schema import (
    MRPCalculationCreate,
    MRPCalculateRequest
)
from base.common.response import success_response

mrp_router = APIRouter(prefix="/mrp", tags=["物料需求计划"])

@mrp_router.get("", summary="获取MRP计算列表")
async def list_mrp(
    page: int = 1,
    page_size: int = 10,
    mrp_code: Optional[str] = None,
    mrp_name: Optional[str] = None,
    status: Optional[str] = None,
    mps_code: Optional[str] = None
):
    items, total = await MRPService.get_list(
        page=page, page_size=page_size,
        mrp_code=mrp_code,
        mrp_name=mrp_name,
        status=status,
        mps_code=mps_code
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@mrp_router.get("/{mrp_id}/details", summary="获取MRP计算结果明细")
async def get_mrp_details(mrp_id: int):
    details = await MRPService.get_mrp_details(mrp_id)
    return success_response(data=details)

@mrp_router.get("/{mrp_id}/planned-orders", summary="获取MRP计划订单列表")
async def get_mrp_planned_orders(mrp_id: int):
    items, total = await PlannedOrderService.get_list(mrp_id=mrp_id, page_size=1000)
    return success_response(data={"items": items, "total": total})

@mrp_router.post("", summary="创建MRP计算")
async def create_mrp(data: MRPCalculationCreate):
    try:
        mrp = await MRPService.create_mrp(data)
        return success_response(data=mrp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mrp_router.post("/calculate", summary="执行MRP计算")
async def calculate_mrp(data: MRPCalculateRequest):
    try:
        mrp = await MRPService.calculate_mrp(data)
        return success_response(data=mrp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mrp_router.get("/{mrp_id}", summary="获取MRP计算详情")
async def get_mrp(mrp_id: int):
    mrp = await MRPService.get_by_id(mrp_id)
    if not mrp:
        raise HTTPException(status_code=404, detail="MRP计算不存在")
    details = await MRPService.get_mrp_details(mrp_id)
    result = await mrp.to_dict()
    result['details'] = [await d.to_dict() for d in details]
    return success_response(data=result)

@mrp_router.delete("/{mrp_id}", summary="删除MRP计算")
async def delete_mrp(mrp_id: int):
    success = await MRPService.delete_mrp(mrp_id)
    if not success:
        raise HTTPException(status_code=404, detail="MRP计算不存在")
    return success_response(data={"message": "MRP计算删除成功"}, msg="MRP计算删除成功")