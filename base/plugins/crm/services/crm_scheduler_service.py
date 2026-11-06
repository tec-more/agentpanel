from datetime import datetime, timedelta
from loguru import logger

from base.plugins.crm.models.lead import Lead, LeadStatus
from base.plugins.crm.models.opportunity import Opportunity, OpportunityStatus
from base.plugins.crm.models.follow_up_task import FollowUpTask, TaskStatus
from base.plugins.crm.models.crm_config import CrmConfig
class CrmSchedulerService:
    model = "crm_scheduler"

    @staticmethod
    async def auto_recycle_leads():
        config = await CrmConfig.get_or_none(config_key="auto_recycle_days")
        days = int(config.config_value) if config else 30
        threshold = datetime.now() - timedelta(days=days)
        leads = await Lead.filter(
            status__in=[LeadStatus.NEW, LeadStatus.CONTACTED],
            last_follow_up_time__lt=threshold,
        )
        count = 0
        for lead in leads:
            lead.status = LeadStatus.INVALID
            await lead.save()
            count += 1
        if count > 0:
            logger.info(f"自动回收线索 {count} 条")
        return count

    @staticmethod
    async def mark_stale_opportunities():
        config = await CrmConfig.get_or_none(config_key="stale_warning_days")
        days = int(config.config_value) if config else 14
        threshold = datetime.now() - timedelta(days=days)
        opps = await Opportunity.filter(
            status=OpportunityStatus.ACTIVE,
            last_follow_up_time__lt=threshold,
        )
        count = 0
        for opp in opps:
            opp.status = OpportunityStatus.STALLED
            await opp.save()
            count += 1
        if count > 0:
            logger.info(f"标记停滞商机 {count} 条")
        return count

    @staticmethod
    async def mark_overdue_tasks():
        now = datetime.now()
        tasks = await FollowUpTask.filter(
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS],
            due_date__lt=now,
        )
        count = 0
        for task in tasks:
            task.status = TaskStatus.OVERDUE
            await task.save()
            count += 1
        if count > 0:
            logger.info(f"标记超期任务 {count} 条")
        return count

    @staticmethod
    async def handle_order_paid(event_name: str, **kwargs):
        order_id = kwargs.get("order_id")
        if not order_id:
            return
        opp = await Opportunity.get_or_none(order_id=order_id)
        if opp:
            logger.info(f"订单 {order_id} 已支付，关联商机 {opp.id}")