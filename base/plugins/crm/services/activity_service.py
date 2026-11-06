from typing import Optional, List, Tuple
from datetime import datetime
from loguru import logger

from base.plugins.crm.models.activity import Activity, ActivityType
from base.plugins.crm.models.lead import Lead, LeadStatus
from base.plugins.crm.models.opportunity import Opportunity
from base.plugins.crm.schemas.activity_schema import ActivityCreate, ActivityListQuery, TimelineQuery
from base.plugins.crm.services.crm_data_filter import get_crm_data_filter
class ActivityService:
    model = "activity"

    @staticmethod
    async def create_activity(activity_data: ActivityCreate, created_by: int) -> Activity:
        if activity_data.lead_id:
            lead = await Lead.get_or_none(id=activity_data.lead_id)
            if not lead:
                raise ValueError("CRM_OBJECT_NOT_FOUND: 关联的线索不存在")
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.CONTACTED
                await lead.save()
            lead.last_follow_up_time = activity_data.activity_time
            await lead.save()
        if activity_data.opportunity_id:
            opp = await Opportunity.get_or_none(id=activity_data.opportunity_id)
            if not opp:
                raise ValueError("CRM_OBJECT_NOT_FOUND: 关联的商机不存在")
            opp.last_follow_up_time = activity_data.activity_time
            await opp.save()
        activity = await Activity.create(
            type=activity_data.type,
            subject=activity_data.subject,
            content=activity_data.content,
            activity_time=activity_data.activity_time,
            lead_id=activity_data.lead_id,
            opportunity_id=activity_data.opportunity_id,
            contact_id=activity_data.contact_id,
            created_by=created_by,
        )
        return activity

    @staticmethod
    async def get_activity_list(query_params: ActivityListQuery, user_id: int) -> Tuple[List[Activity], int]:
        data_filter = await get_crm_data_filter(user_id)
        query = Activity.all()
        if query_params.lead_id is not None:
            query = query.filter(lead_id=query_params.lead_id)
        if query_params.opportunity_id is not None:
            query = query.filter(opportunity_id=query_params.opportunity_id)
        if query_params.type:
            query = query.filter(type=query_params.type)
        total = await query.count()
        offset = (query_params.page - 1) * query_params.page_size
        activities = await query.offset(offset).limit(query_params.page_size).order_by("-activity_time")
        return activities, total

    @staticmethod
    async def get_timeline(query_params: TimelineQuery, user_id: int) -> Tuple[List[Activity], int]:
        query = Activity.all()
        if query_params.lead_id:
            query = query.filter(lead_id=query_params.lead_id)
        elif query_params.opportunity_id:
            query = query.filter(opportunity_id=query_params.opportunity_id)
        else:
            raise ValueError("线索ID或商机ID必须提供一个")
        total = await query.count()
        offset = (query_params.page - 1) * query_params.page_size
        activities = await query.offset(offset).limit(query_params.page_size).order_by("-activity_time")
        return activities, total

    @staticmethod
    async def delete_activity(activity_id: int) -> bool:
        activity = await Activity.get_or_none(id=activity_id)
        if not activity:
            return False
        await activity.delete()
        return True