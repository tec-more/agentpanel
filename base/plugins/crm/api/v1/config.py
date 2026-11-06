from typing import List
from fastapi import APIRouter
from base.common.permissions import require_permission
from base.common.response import success_response, fail_response
from base.plugins.crm.schemas.config_schema import (
    OpportunityStageCreate, OpportunityStageUpdate,
    LeadSourceCreate, LeadSourceUpdate,
    CrmSettingsUpdate,
)
from base.plugins.crm.services.crm_config_service import CrmConfigService

config_router = APIRouter(prefix="/config", tags=["CRM系统配置"])


@config_router.get("/stages")
async def get_stages(
    user_id: int = require_permission("crm:config:view"),
):
    stages = await CrmConfigService.get_stages()
    items = [await s.to_dict() for s in stages]
    return success_response(data=items)


@config_router.post("/stages")
async def save_stage(
    stage_data: OpportunityStageCreate,
    user_id: int = require_permission("crm:config:manage"),
):
    try:
        stage = await CrmConfigService.save_stage(stage_data)
        return success_response(data=await stage.to_dict(), msg="商机阶段保存成功")
    except Exception as e:
        return fail_response(msg=str(e))


@config_router.put("/stages/{stage_id}")
async def update_stage(
    stage_id: int,
    stage_data: OpportunityStageUpdate,
    user_id: int = require_permission("crm:config:manage"),
):
    stage = await CrmConfigService.update_stage(stage_id, stage_data)
    if not stage:
        return fail_response(msg="阶段不存在", code=404)
    return success_response(data=await stage.to_dict(), msg="商机阶段更新成功")


@config_router.delete("/stages/{stage_id}")
async def delete_stage(
    stage_id: int,
    user_id: int = require_permission("crm:config:manage"),
):
    try:
        result = await CrmConfigService.delete_stage(stage_id)
        if not result:
            return fail_response(msg="阶段不存在", code=404)
        return success_response(msg="商机阶段删除成功")
    except ValueError as e:
        return fail_response(msg=str(e))


@config_router.get("/lead-sources")
async def get_lead_sources(
    user_id: int = require_permission("crm:config:view"),
):
    sources = await CrmConfigService.get_lead_sources()
    items = [await s.to_dict() for s in sources]
    return success_response(data=items)


@config_router.post("/lead-sources")
async def save_lead_source(
    source_data: LeadSourceCreate,
    user_id: int = require_permission("crm:config:manage"),
):
    try:
        source = await CrmConfigService.save_lead_source(source_data)
        return success_response(data=await source.to_dict(), msg="线索来源保存成功")
    except Exception as e:
        return fail_response(msg=str(e))


@config_router.put("/lead-sources/{source_id}")
async def update_lead_source(
    source_id: int,
    source_data: LeadSourceUpdate,
    user_id: int = require_permission("crm:config:manage"),
):
    source = await CrmConfigService.update_lead_source(source_id, source_data)
    if not source:
        return fail_response(msg="线索来源不存在", code=404)
    return success_response(data=await source.to_dict(), msg="线索来源更新成功")


@config_router.delete("/lead-sources/{source_id}")
async def delete_lead_source(
    source_id: int,
    user_id: int = require_permission("crm:config:manage"),
):
    result = await CrmConfigService.delete_lead_source(source_id)
    if not result:
        return fail_response(msg="线索来源不存在", code=404)
    return success_response(msg="线索来源删除成功")


@config_router.get("/settings")
async def get_settings(
    user_id: int = require_permission("crm:config:view"),
):
    settings = await CrmConfigService.get_settings()
    return success_response(data=settings.model_dump())


@config_router.put("/settings")
async def update_settings(
    settings_data: CrmSettingsUpdate,
    user_id: int = require_permission("crm:config:manage"),
):
    settings = await CrmConfigService.update_settings(settings_data)
    return success_response(data=settings.model_dump(), msg="系统配置更新成功")