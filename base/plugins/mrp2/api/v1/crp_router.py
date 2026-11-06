from typing import Optional
from fastapi import APIRouter, HTTPException

from base.plugins.mrp2.services.mrp_service import CRPService
from base.plugins.mrp2.schemas.mrp_schema import (
    CRPCreate,
    CRPCalculateRequest
)
from base.common.response import success_response

crp_router = APIRouter(prefix="/crp", tags=["能力需求计划"])

@crp_router.get("", summary="获取CRP计算列表")
async def list_crp(
    page: int = 1,
    page_size: int = 10,
    crp_code: Optional[str] = None,
    crp_name: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await CRPService.get_list(
        page=page, page_size=page_size,
        crp_code=crp_code,
        crp_name=crp_name,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@crp_router.get("/{crp_id}/details", summary="获取CRP计算结果明细")
async def get_crp_details(crp_id: int):
    details = await CRPService.get_crp_details(crp_id)
    return success_response(data=details)

@crp_router.post("", summary="创建CRP计算")
async def create_crp(data: CRPCreate):
    try:
        crp = await CRPService.create_crp(data)
        return success_response(data=crp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@crp_router.post("/calculate", summary="执行CRP计算")
async def calculate_crp(data: CRPCalculateRequest):
    try:
        crp = await CRPService.calculate_crp(data)
        return success_response(data=crp)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@crp_router.get("/{crp_id}", summary="获取CRP计算详情")
async def get_crp(crp_id: int):
    crp = await CRPService.get_by_id(crp_id)
    if not crp:
        raise HTTPException(status_code=404, detail="CRP计算不存在")
    details = await CRPService.get_crp_details(crp_id)
    result = await crp.to_dict()
    result['details'] = [await d.to_dict() for d in details]
    return success_response(data=result)

@crp_router.delete("/{crp_id}", summary="删除CRP计算")
async def delete_crp(crp_id: int):
    success = await CRPService.delete_crp(crp_id)
    if not success:
        raise HTTPException(status_code=404, detail="CRP计算不存在")
    return success_response(data={"message": "CRP计算删除成功"}, msg="CRP计算删除成功")