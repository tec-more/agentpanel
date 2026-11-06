from typing import Optional
from fastapi import APIRouter, HTTPException

from base.plugins.mrp2.services.mrp_service import SalesForecastService
from base.plugins.mrp2.schemas.mrp_schema import (
    SalesForecastCreate, SalesForecastUpdate,
    SalesForecastDetailCreate
)
from base.common.response import success_response

forecast_router = APIRouter(prefix="/forecast", tags=["销售预测"])

@forecast_router.get("", summary="获取销售预测列表")
async def list_forecasts(
    page: int = 1,
    page_size: int = 10,
    forecast_code: Optional[str] = None,
    forecast_name: Optional[str] = None,
    forecast_type: Optional[str] = None,
    status: Optional[str] = None
):
    items, total = await SalesForecastService.get_list(
        page=page, page_size=page_size,
        forecast_code=forecast_code,
        forecast_name=forecast_name,
        forecast_type=forecast_type,
        status=status
    )
    return success_response(data={"items": items, "total": total, "page": page, "page_size": page_size})

@forecast_router.get("/{forecast_id}/details", summary="获取销售预测明细")
async def get_forecast_details(forecast_id: int):
    details = await SalesForecastService.get_forecast_details(forecast_id)
    return success_response(data=details)

@forecast_router.post("/{forecast_id}/details", summary="添加销售预测明细")
async def add_forecast_detail(forecast_id: int, data: dict):
    data['forecast_id'] = forecast_id
    try:
        detail = await SalesForecastService.create_forecast_detail(data)
        return success_response(data=detail)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@forecast_router.put("/details/{detail_id}", summary="更新销售预测明细")
async def update_forecast_detail(detail_id: int, data: dict):
    detail = await SalesForecastService.update_forecast_detail(detail_id, data)
    if not detail:
        raise HTTPException(status_code=404, detail="销售预测明细不存在")
    return success_response(data=detail)

@forecast_router.delete("/details/{detail_id}", summary="删除销售预测明细")
async def delete_forecast_detail(detail_id: int):
    success = await SalesForecastService.delete_forecast_detail(detail_id)
    if not success:
        raise HTTPException(status_code=404, detail="销售预测明细不存在")
    return success_response(data={"message": "销售预测明细删除成功"}, msg="销售预测明细删除成功")

@forecast_router.put("/{forecast_id}/submit", summary="提交审核")
async def submit_forecast(forecast_id: int):
    try:
        forecast = await SalesForecastService.submit_for_review(forecast_id)
        if not forecast:
            raise HTTPException(status_code=404, detail="销售预测不存在")
        return success_response(data=forecast)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@forecast_router.put("/{forecast_id}/approve", summary="审批通过")
async def approve_forecast(forecast_id: int):
    try:
        forecast = await SalesForecastService.approve_forecast(forecast_id)
        if not forecast:
            raise HTTPException(status_code=404, detail="销售预测不存在")
        return success_response(data=forecast)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@forecast_router.put("/{forecast_id}/reject", summary="驳回")
async def reject_forecast(forecast_id: int):
    try:
        forecast = await SalesForecastService.reject_forecast(forecast_id)
        if not forecast:
            raise HTTPException(status_code=404, detail="销售预测不存在")
        return success_response(data=forecast)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@forecast_router.post("", summary="创建销售预测")
async def create_forecast(data: SalesForecastCreate):
    try:
        forecast = await SalesForecastService.create_forecast(data)
        return success_response(data=forecast)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@forecast_router.get("/{forecast_id}", summary="获取销售预测详情")
async def get_forecast(forecast_id: int):
    forecast = await SalesForecastService.get_by_id(forecast_id)
    if not forecast:
        raise HTTPException(status_code=404, detail="销售预测不存在")
    details = await SalesForecastService.get_forecast_details(forecast_id)
    result = await forecast.to_dict()
    result['details'] = [await d.to_dict() for d in details]
    return success_response(data=result)

@forecast_router.put("/{forecast_id}", summary="更新销售预测")
async def update_forecast(forecast_id: int, data: SalesForecastUpdate):
    try:
        forecast = await SalesForecastService.update_forecast(forecast_id, data)
        if not forecast:
            raise HTTPException(status_code=404, detail="销售预测不存在")
        return success_response(data=forecast)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@forecast_router.delete("/{forecast_id}", summary="删除销售预测")
async def delete_forecast(forecast_id: int):
    success = await SalesForecastService.delete_forecast(forecast_id)
    if not success:
        raise HTTPException(status_code=404, detail="销售预测不存在")
    return success_response(data={"message": "销售预测删除成功"}, msg="销售预测删除成功")

@forecast_router.get("/generate/{product_code}", summary="根据历史数据生成预测")
async def generate_forecast(product_code: str, months: int = 6):
    result = await SalesForecastService.generate_from_history(product_code, months)
    return success_response(data=result)