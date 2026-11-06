from typing import List
from decimal import Decimal
from datetime import datetime
from loguru import logger

from base.plugins.crm.models.lead import Lead, LeadStatus
from base.plugins.crm.models.opportunity import Opportunity, OpportunityStatus
from base.plugins.crm.models.opportunity_stage import OpportunityStage
from base.plugins.crm.models.lead_source import LeadSource
from base.plugins.crm.models.activity import Activity
from base.plugins.crm.models.contact import Contact
from base.plugins.crm.schemas.stats_schema import (
    FunnelStageStats, FunnelStatsResponse, LeadSourceStats,
    LeadSourceStatsResponse, SalesPerformanceStats,
    SalesPerformanceResponse, CustomerFollowUpStats,
    CustomerFollowUpResponse,
)
from base.plugins.crm.services.crm_data_filter import get_crm_data_filter


class CrmStatsService:

    @staticmethod
    async def get_funnel_stats(user_id: int) -> FunnelStatsResponse:
        data_filter = await get_crm_data_filter(user_id)
        stages = await OpportunityStage.filter(is_active=True).order_by("sort_order")
        stage_stats = []
        total_opportunities = 0
        total_amount = Decimal("0")
        for stage in stages:
            query = Opportunity.filter(stage=stage.code, status=OpportunityStatus.ACTIVE)
            if data_filter:
                query = query.filter(**data_filter)
            count = await query.count()
            amount_query = Opportunity.filter(stage=stage.code, status=OpportunityStatus.ACTIVE)
            if data_filter:
                amount_query = amount_query.filter(**data_filter)
            opps_for_amount = await amount_query
            amounts = [float(o.expected_amount) for o in opps_for_amount]
            total = Decimal(str(sum(amounts)))
            total_opportunities += count
            total_amount += total
            stage_stats.append(FunnelStageStats(
                stage_code=stage.code,
                stage_name=stage.name,
                opportunity_count=count,
                total_expected_amount=total,
                conversion_rate=0.0,
            ))
        for i in range(len(stage_stats) - 1):
            current = stage_stats[i].opportunity_count
            next_count = stage_stats[i + 1].opportunity_count
            if current > 0:
                stage_stats[i].conversion_rate = round(next_count / current * 100, 2)
        return FunnelStatsResponse(
            stages=stage_stats,
            total_opportunities=total_opportunities,
            total_amount=total_amount,
        )

    @staticmethod
    async def get_lead_source_stats(user_id: int) -> LeadSourceStatsResponse:
        data_filter = await get_crm_data_filter(user_id)
        sources = await LeadSource.filter(is_active=True).order_by("sort_order")
        source_stats = []
        for source in sources:
            query = Lead.filter(source=source.code)
            if data_filter:
                query = query.filter(**data_filter)
            lead_count = await query.count()
            converted_query = Lead.filter(source=source.code, status=LeadStatus.CONVERTED)
            if data_filter:
                converted_query = converted_query.filter(**data_filter)
            converted = await converted_query.count()
            conversion_rate = round(converted / lead_count * 100, 2) if lead_count > 0 else 0.0
            source_stats.append(LeadSourceStats(
                source_code=source.code,
                source_name=source.name,
                lead_count=lead_count,
                converted_count=converted,
                conversion_rate=conversion_rate,
            ))
        return LeadSourceStatsResponse(sources=source_stats)

    @staticmethod
    async def get_sales_performance(user_id: int) -> SalesPerformanceResponse:
        data_filter = await get_crm_data_filter(user_id)
        won_opps = Opportunity.filter(status=OpportunityStatus.WON)
        if data_filter:
            won_opps = won_opps.filter(**data_filter)
        won_list = await won_opps.all()
        user_stats = {}
        for opp in won_list:
            uid = opp.assigned_to or 0
            if uid not in user_stats:
                user_stats[uid] = {"opportunity_count": 0, "won_amount": Decimal("0"), "close_days": []}
            user_stats[uid]["opportunity_count"] += 1
            user_stats[uid]["won_amount"] += opp.actual_amount or Decimal("0")
            if opp.won_at and opp.created_at:
                days = (opp.won_at - opp.created_at).days
                user_stats[uid]["close_days"].append(days)
        performances = []
        for uid, stats in user_stats.items():
            user_name = str(uid)
            try:
                from base.core.users.models.users import User
                user = await User.get_or_none(id=uid)
                if user:
                    user_name = user.username or str(uid)
            except Exception:
                pass
            avg_days = round(sum(stats["close_days"]) / len(stats["close_days"]), 1) if stats["close_days"] else 0.0
            performances.append(SalesPerformanceStats(
                user_id=uid,
                user_name=user_name,
                opportunity_count=stats["opportunity_count"],
                won_amount=stats["won_amount"],
                avg_close_days=avg_days,
            ))
        return SalesPerformanceResponse(performances=performances)

    @staticmethod
    async def get_customer_follow_up(user_id: int) -> CustomerFollowUpResponse:
        data_filter = await get_crm_data_filter(user_id)
        opps = Opportunity.filter(status=OpportunityStatus.ACTIVE)
        if data_filter:
            opps = opps.filter(**data_filter)
        active_opps = await opps.all()
        customer_ids = list(set(o.customer_id for o in active_opps))
        follow_ups = []
        for cid in customer_ids:
            customer_name = str(cid)
            try:
                from base.plugins.customer.models.customer import Customer
                customer = await Customer.get_or_none(id=cid)
                if customer:
                    customer_name = customer.nickname or customer.username or str(cid)
            except Exception:
                pass
            last_activity = await Activity.filter(
                opportunity_id__in=[o.id for o in active_opps if o.customer_id == cid]
            ).order_by("-activity_time").first()
            activity_count = await Activity.filter(
                opportunity_id__in=[o.id for o in active_opps if o.customer_id == cid]
            ).count()
            active_opp_count = sum(1 for o in active_opps if o.customer_id == cid)
            follow_ups.append(CustomerFollowUpStats(
                customer_id=cid,
                customer_name=customer_name,
                last_follow_up_time=last_activity.activity_time.isoformat() if last_activity and last_activity.activity_time else None,
                activity_count=activity_count,
                active_opportunity_count=active_opp_count,
            ))
        return CustomerFollowUpResponse(follow_ups=follow_ups)