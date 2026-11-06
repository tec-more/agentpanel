from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, Field


class FunnelStageStats(BaseModel):
    stage_code: str
    stage_name: str
    opportunity_count: int
    total_expected_amount: Decimal
    conversion_rate: float = 0.0


class FunnelStatsResponse(BaseModel):
    stages: List[FunnelStageStats]
    total_opportunities: int
    total_amount: Decimal


class LeadSourceStats(BaseModel):
    source_code: str
    source_name: str
    lead_count: int
    converted_count: int
    conversion_rate: float = 0.0


class LeadSourceStatsResponse(BaseModel):
    sources: List[LeadSourceStats]


class SalesPerformanceStats(BaseModel):
    user_id: int
    user_name: str
    opportunity_count: int
    won_amount: Decimal
    avg_close_days: float = 0.0


class SalesPerformanceResponse(BaseModel):
    performances: List[SalesPerformanceStats]


class CustomerFollowUpStats(BaseModel):
    customer_id: int
    customer_name: str
    last_follow_up_time: Optional[str] = None
    activity_count: int
    active_opportunity_count: int


class CustomerFollowUpResponse(BaseModel):
    follow_ups: List[CustomerFollowUpStats]