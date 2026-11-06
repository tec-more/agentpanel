from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from base.common.response import SuccessResponse

try:
    from base.plugins.finance.services.integration_account_mapping_service import IntegrationAccountMappingService
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

integration_account_mapping_router = APIRouter(prefix="/integration-account-mappings", tags=["集成科目映射"])


class CreateMappingRequest(BaseModel):
    event_type: str
    debit_account_code: str
    credit_account_code: str
    is_active: bool = True
    description: Optional[str] = None


class UpdateMappingRequest(BaseModel):
    event_type: Optional[str] = None
    debit_account_code: Optional[str] = None
    credit_account_code: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


@integration_account_mapping_router.get("/", summary="获取科目映射列表")
async def get_mappings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    event_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    total = await IntegrationAccountMappingService.get_mapping_count(event_type=event_type, is_active=is_active)
    items = await IntegrationAccountMappingService.get_all_mappings(page=page, page_size=page_size, event_type=event_type, is_active=is_active)
    data = [await item.to_dict() for item in items]
    return SuccessResponse(data={"total": total, "page": page, "page_size": page_size, "data": data})


@integration_account_mapping_router.get("/{mapping_id}", summary="获取科目映射详情")
async def get_mapping(mapping_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    mapping = await IntegrationAccountMappingService.get_mapping_by_id(mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="科目映射不存在")
    return SuccessResponse(data=await mapping.to_dict())


@integration_account_mapping_router.post("/", summary="创建科目映射")
async def create_mapping(req: CreateMappingRequest):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    mapping = await IntegrationAccountMappingService.create_mapping(req.model_dump())
    return SuccessResponse(data=await mapping.to_dict(), msg="创建成功")


@integration_account_mapping_router.put("/{mapping_id}", summary="更新科目映射")
async def update_mapping(mapping_id: int, req: UpdateMappingRequest):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    mapping = await IntegrationAccountMappingService.update_mapping(mapping_id, data)
    if not mapping:
        raise HTTPException(status_code=404, detail="科目映射不存在")
    return SuccessResponse(data=await mapping.to_dict(), msg="更新成功")


@integration_account_mapping_router.delete("/{mapping_id}", summary="删除科目映射")
async def delete_mapping(mapping_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    success = await IntegrationAccountMappingService.delete_mapping(mapping_id)
    if not success:
        raise HTTPException(status_code=404, detail="科目映射不存在")
    return SuccessResponse(msg="删除成功")


@integration_account_mapping_router.post("/{mapping_id}/toggle", summary="启用/禁用科目映射")
async def toggle_mapping(mapping_id: int):
    if not FINANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="财务模块不可用")
    mapping = await IntegrationAccountMappingService.toggle_mapping(mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="科目映射不存在")
    return SuccessResponse(data=await mapping.to_dict(), msg="操作成功")