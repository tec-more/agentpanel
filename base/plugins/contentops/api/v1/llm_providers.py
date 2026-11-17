"""LLM 供应商配置路由（M4，仅境内节点）。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from base.common.authz import OwnerContext, require_owner, require_action
from base.common.response import success_response, fail_response
from base.plugins.contentops.schemas.content_schema import LLMProviderCreate, LLMProviderUpdate
from base.plugins.contentops.services.llm_provider_service import LLMProviderService

llm_providers_router = APIRouter(prefix="/llm-providers", tags=["LLM供应商配置"])


@llm_providers_router.post("", summary="新建 LLM 供应商配置")
async def create_config(
    data: LLMProviderCreate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    try:
        return success_response(data=await LLMProviderService.create(data, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=400)


@llm_providers_router.get("", summary="LLM 供应商配置列表")
async def list_configs(
    purpose: Optional[str] = Query(None),
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:view"),
):
    return success_response(data={"items": await LLMProviderService.list_configs(purpose, owner)})


@llm_providers_router.put("/{cfg_id}", summary="编辑 LLM 供应商配置")
async def update_config(
    cfg_id: int, data: LLMProviderUpdate,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    try:
        return success_response(data=await LLMProviderService.update(cfg_id, data, owner))
    except ValueError as e:
        return fail_response(msg=str(e), code=404)


@llm_providers_router.delete("/{cfg_id}", summary="删除 LLM 供应商配置")
async def delete_config(
    cfg_id: int,
    owner: OwnerContext = Depends(require_owner),
    user_id: int = require_action("contentops:rule:manage"),
):
    try:
        await LLMProviderService.delete(cfg_id, owner)
        return success_response(msg="删除成功")
    except ValueError as e:
        return fail_response(msg=str(e), code=404)
