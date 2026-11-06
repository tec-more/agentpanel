from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from base.plugins.mrp2.services.mrp_service import MPSService
from base.plugins.mrp2.schemas.mrp_schema import (
    MPSCreate, MPSUpdate,
    MPSDetailCreate
)
from base.plugins.mrp2.schemas.mps_plan_line_schema import (
    CompileMPSRequest, ApproveMPSRequest, MPSLineAdjustment, MPSPlanLineCreate
)
from base.common.response import success_response
from base.common.security import get_current_user_id

mps_router = APIRouter(prefix="/mps", tags=["主生产计划"])

@mps_router.get("", summary="获取主生产计划列表")
async def list_mps(
    page: int = 1,
    page_size: int = 10,
    mps_code: Optional[str] = None,
    mps_name: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await MPSService.get_list(
        page=page, page_size=page_size,
        mps_code=mps_code,
        mps_name=mps_name,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@mps_router.get("/{mps_id}/details", summary="获取主生产计划明细")
async def get_mps_details(mps_id: int):
    details = await MPSService.get_mps_details(mps_id)
    return success_response(data=details)

@mps_router.get("/{mps_id}/plan-lines", summary="获取MPS计划行")
async def get_plan_lines(mps_id: int):
    lines = await MPSService.get_plan_lines(mps_id)
    return success_response(data=lines)

@mps_router.post("/{mps_id}/details", summary="添加主生产计划明细")
async def add_mps_detail(mps_id: int, data: dict):
    data['mps_id'] = mps_id
    try:
        detail = await MPSService.create_mps_detail(data)
        return success_response(data=detail)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.put("/details/{detail_id}", summary="更新主生产计划明细")
async def update_mps_detail(detail_id: int, data: dict):
    detail = await MPSService.update_mps_detail(detail_id, data)
    if not detail:
        raise HTTPException(status_code=404, detail="主生产计划明细不存在")
    return success_response(data=detail)

@mps_router.delete("/details/{detail_id}", summary="删除主生产计划明细")
async def delete_mps_detail(detail_id: int):
    success = await MPSService.delete_mps_detail(detail_id)
    if not success:
        raise HTTPException(status_code=404, detail="主生产计划明细不存在")
    return success_response(data={"message": "主生产计划明细删除成功"}, msg="主生产计划明细删除成功")

@mps_router.post("/{mps_id}/compile", summary="编制主生产计划")
async def compile_mps(mps_id: int):
    try:
        result = await MPSService.compile_mps(mps_id)
        return success_response(data=result, msg="MPS编制完成")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.put("/{mps_id}/submit", summary="提交审核")
async def submit_mps(mps_id: int):
    try:
        mps = await MPSService.submit_for_review(mps_id)
        if not mps:
            raise HTTPException(status_code=404, detail="主生产计划不存在")
        return success_response(data=mps, msg="MPS已提交审核")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.put("/{mps_id}/approve", summary="审批MPS")
async def approve_mps(mps_id: int, data: ApproveMPSRequest, user_id: str = Depends(get_current_user_id)):
    try:
        mps = await MPSService.approve_mps(
            mps_id,
            approved=data.approved,
            approved_by=user_id,
            remark=data.remark
        )
        if not mps:
            raise HTTPException(status_code=404, detail="主生产计划不存在")
        return success_response(data=mps, msg="MPS审批通过" if data.approved else "MPS审批驳回")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.put("/{mps_id}/release", summary="下达MPS")
async def release_mps(mps_id: int, user_id: str = Depends(get_current_user_id)):
    try:
        mps = await MPSService.release_mps(mps_id, released_by=user_id)
        if not mps:
            raise HTTPException(status_code=404, detail="主生产计划不存在")
        return success_response(data=mps, msg="MPS已下达")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.put("/{mps_id}/close", summary="关闭MPS")
async def close_mps(mps_id: int):
    try:
        mps = await MPSService.close_mps(mps_id)
        if not mps:
            raise HTTPException(status_code=404, detail="主生产计划不存在")
        return success_response(data=mps, msg="MPS已关闭")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.put("/{mps_id}/cancel", summary="取消MPS")
async def cancel_mps(mps_id: int):
    try:
        mps = await MPSService.cancel_mps(mps_id)
        if not mps:
            raise HTTPException(status_code=404, detail="主生产计划不存在")
        return success_response(data=mps, msg="MPS已取消")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.put("/plan-lines/{line_id}/adjust", summary="调整MPS计划行")
async def adjust_plan_line(line_id: int, data: MPSLineAdjustment):
    try:
        line = await MPSService.adjust_plan_line(line_id, data)
        if not line:
            raise HTTPException(status_code=404, detail="计划行不存在")
        return success_response(data=line, msg="计划行调整成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.post("/{mps_id}/plan-lines", summary="添加MPS计划行")
async def add_plan_line(mps_id: int, data: MPSPlanLineCreate):
    try:
        line = await MPSService.add_plan_line(mps_id, data)
        return success_response(data=line, msg="计划行添加成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.post("", summary="创建主生产计划")
async def create_mps(data: MPSCreate):
    try:
        mps = await MPSService.create_mps(data)
        return success_response(data=mps)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.post("/generate", summary="基于销售预测生成MPS")
async def generate_mps(data: dict):
    forecast_id = data.get('forecast_id')
    if not forecast_id:
        raise HTTPException(status_code=400, detail="销售预测ID不能为空")
    try:
        result = await MPSService.generate_from_forecast(forecast_id)
        return success_response(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.get("/{mps_id}", summary="获取主生产计划详情")
async def get_mps(mps_id: int):
    mps = await MPSService.get_by_id(mps_id)
    if not mps:
        raise HTTPException(status_code=404, detail="主生产计划不存在")
    details = await MPSService.get_mps_details(mps_id)
    plan_lines = await MPSService.get_plan_lines(mps_id)
    result = await mps.to_dict()
    result['details'] = [await d.to_dict() for d in details]
    result['plan_lines'] = [await pl.to_dict() for pl in plan_lines]
    return success_response(data=result)

@mps_router.put("/{mps_id}", summary="更新主生产计划")
async def update_mps(mps_id: int, data: MPSUpdate):
    try:
        mps = await MPSService.update_mps(mps_id, data)
        if not mps:
            raise HTTPException(status_code=404, detail="主生产计划不存在")
        return success_response(data=mps)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@mps_router.delete("/{mps_id}", summary="删除主生产计划")
async def delete_mps(mps_id: int):
    success = await MPSService.delete_mps(mps_id)
    if not success:
        raise HTTPException(status_code=404, detail="主生产计划不存在")
    return success_response(data={"message": "主生产计划删除成功"}, msg="主生产计划删除成功")
