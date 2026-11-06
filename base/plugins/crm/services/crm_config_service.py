from typing import Optional, List
from loguru import logger

from base.plugins.crm.models.opportunity_stage import OpportunityStage
from base.plugins.crm.models.lead_source import LeadSource
from base.plugins.crm.models.crm_config import CrmConfig
from base.plugins.crm.models.opportunity import Opportunity
from base.plugins.crm.schemas.config_schema import (
    OpportunityStageCreate, OpportunityStageUpdate,
    LeadSourceCreate, LeadSourceUpdate,
    CrmSettingsUpdate, CrmSettingsResponse,
)
class CrmConfigService:
    model = "crm_config"

    @staticmethod
    async def initialize_default_data():
        stages = await OpportunityStage.all().count()
        if stages == 0:
            default_stages = [
                {"name": "初步接触", "code": "initial_contact", "sort_order": 1, "probability": 10},
                {"name": "需求确认", "code": "requirement_confirmation", "sort_order": 2, "probability": 25},
                {"name": "方案报价", "code": "proposal_quotation", "sort_order": 3, "probability": 50},
                {"name": "商务谈判", "code": "negotiation", "sort_order": 4, "probability": 75},
                {"name": "赢单", "code": "won", "sort_order": 5, "probability": 100, "is_won_stage": True},
                {"name": "输单", "code": "lost", "sort_order": 6, "probability": 0, "is_lost_stage": True},
            ]
            for s in default_stages:
                await OpportunityStage.create(**s)
            logger.info("已初始化默认商机阶段数据")

        sources = await LeadSource.all().count()
        if sources == 0:
            default_sources = [
                {"name": "官网注册", "code": "website", "sort_order": 1},
                {"name": "广告投放", "code": "advertisement", "sort_order": 2},
                {"name": "转介绍", "code": "referral", "sort_order": 3},
                {"name": "展会", "code": "exhibition", "sort_order": 4},
                {"name": "其他", "code": "other", "sort_order": 5},
            ]
            for s in default_sources:
                await LeadSource.create(**s)
            logger.info("已初始化默认线索来源数据")

        auto_recycle = await CrmConfig.get_or_none(config_key="auto_recycle_days")
        if not auto_recycle:
            await CrmConfig.create(config_key="auto_recycle_days", config_value="30", description="线索自动回收天数")
        stale_warning = await CrmConfig.get_or_none(config_key="stale_warning_days")
        if not stale_warning:
            await CrmConfig.create(config_key="stale_warning_days", config_value="14", description="商机超期预警天数")
        logger.info("已初始化默认CRM系统配置")

    @staticmethod
    async def get_stages() -> List[OpportunityStage]:
        return await OpportunityStage.filter().order_by("sort_order")

    @staticmethod
    async def save_stage(stage_data: OpportunityStageCreate) -> OpportunityStage:
        existing = await OpportunityStage.get_or_none(code=stage_data.code)
        if existing:
            update_data = stage_data.model_dump(exclude_unset=True)
            await existing.update_from_dict(update_data).save()
            return existing
        return await OpportunityStage.create(**stage_data.model_dump())

    @staticmethod
    async def update_stage(stage_id: int, stage_data: OpportunityStageUpdate) -> Optional[OpportunityStage]:
        stage = await OpportunityStage.get_or_none(id=stage_id)
        if not stage:
            return None
        update_data = stage_data.model_dump(exclude_unset=True)
        await stage.update_from_dict(update_data).save()
        return stage

    @staticmethod
    async def delete_stage(stage_id: int) -> bool:
        stage = await OpportunityStage.get_or_none(id=stage_id)
        if not stage:
            return False
        has_opp = await Opportunity.filter(stage=stage.code).exists()
        if has_opp:
            raise ValueError("CRM_STAGE_IN_USE: 该阶段有商机关联，无法删除")
        await stage.delete()
        return True

    @staticmethod
    async def get_lead_sources() -> List[LeadSource]:
        return await LeadSource.filter().order_by("sort_order")

    @staticmethod
    async def save_lead_source(source_data: LeadSourceCreate) -> LeadSource:
        existing = await LeadSource.get_or_none(code=source_data.code)
        if existing:
            update_data = source_data.model_dump(exclude_unset=True)
            await existing.update_from_dict(update_data).save()
            return existing
        return await LeadSource.create(**source_data.model_dump())

    @staticmethod
    async def update_lead_source(source_id: int, source_data: LeadSourceUpdate) -> Optional[LeadSource]:
        source = await LeadSource.get_or_none(id=source_id)
        if not source:
            return None
        update_data = source_data.model_dump(exclude_unset=True)
        await source.update_from_dict(update_data).save()
        return source

    @staticmethod
    async def delete_lead_source(source_id: int) -> bool:
        source = await LeadSource.get_or_none(id=source_id)
        if not source:
            return False
        await source.delete()
        return True

    @staticmethod
    async def get_settings() -> CrmSettingsResponse:
        auto_recycle = await CrmConfig.get_or_none(config_key="auto_recycle_days")
        stale_warning = await CrmConfig.get_or_none(config_key="stale_warning_days")
        return CrmSettingsResponse(
            auto_recycle_days=int(auto_recycle.config_value) if auto_recycle else 30,
            stale_warning_days=int(stale_warning.config_value) if stale_warning else 14,
        )

    @staticmethod
    async def update_settings(settings_data: CrmSettingsUpdate) -> CrmSettingsResponse:
        if settings_data.auto_recycle_days is not None:
            await CrmConfig.update_or_create(
                config_key="auto_recycle_days",
                defaults={"config_value": str(settings_data.auto_recycle_days), "description": "线索自动回收天数"},
            )
        if settings_data.stale_warning_days is not None:
            await CrmConfig.update_or_create(
                config_key="stale_warning_days",
                defaults={"config_value": str(settings_data.stale_warning_days), "description": "商机超期预警天数"},
            )
        return await CrmConfigService.get_settings()