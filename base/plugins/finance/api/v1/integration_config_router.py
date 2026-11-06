from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from base.common.response import SuccessResponse

try:
    from base.plugins.finance.services.integration_config_service import IntegrationConfigService
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

integration_config_router = APIRouter(prefix="/integration-configs", tags=["集成配置"])


class CreateConfigRequest(BaseModel):
    config_key: str
    config_value: str
    description: Optional[str] = None


class UpdateConfigRequest(BaseModel):
    config_key: Optional[str] = None
    config_value: Optional[str] = None
    description: Optional[str] = None


class SetConfigRequest(BaseModel):
    config_key: str
    config_value: str
    description: Optional[str] = None


@integration_config_router.get("/", summary="获取集成配置列表")
async def get_configs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    total = await IntegrationConfigService.get_config_count()
    items = await IntegrationConfigService.get_all_configs(page=page, page_size=page_size)
    data = [await item.to_dict() for item in items]
    return SuccessResponse(data={"total": total, "page": page, "page_size": page_size, "data": data})


@integration_config_router.get("/{config_id}", summary="获取集成配置详情")
async def get_config(config_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    config = await IntegrationConfigService.get_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return SuccessResponse(data=await config.to_dict())


@integration_config_router.post("/", summary="创建集成配置")
async def create_config(req: CreateConfigRequest):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    config = await IntegrationConfigService.create_config(req.model_dump())
    return SuccessResponse(data=await config.to_dict(), msg="创建成功")


@integration_config_router.put("/{config_id}", summary="更新集成配置")
async def update_config(config_id: int, req: UpdateConfigRequest):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    config = await IntegrationConfigService.update_config(config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    return SuccessResponse(data=await config.to_dict(), msg="更新成功")


@integration_config_router.delete("/{config_id}", summary="删除集成配置")
async def delete_config(config_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    success = await IntegrationConfigService.delete_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="配置不存在")
    return SuccessResponse(msg="删除成功")


@integration_config_router.post("/set", summary="设置配置值（不存在则创建）")
async def set_config(req: SetConfigRequest):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    config = await IntegrationConfigService.set_config_value(
        config_key=req.config_key,
        config_value=req.config_value,
        description=req.description,
    )
    return SuccessResponse(data=await config.to_dict(), msg="设置成功")