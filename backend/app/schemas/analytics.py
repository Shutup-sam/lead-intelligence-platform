from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class AnalyticsOverviewResponse(BaseModel):
    total_leads: int
    qualified_leads: int
    qualification_rate: float
    total_crawls: int
    pages_crawled: int
    jobs_completed: int
    jobs_failed: int
    estimated_ai_cost: float


class DailyUsageItem(BaseModel):
    date: str
    crawls: int
    pages_crawled: int
    leads_created: int
    ai_qualifications: int
    embeddings_generated: int
    jobs_completed: int
    jobs_failed: int
    estimated_ai_cost: float


class AnalyticsUsageResponse(BaseModel):
    items: List[DailyUsageItem]


class CampaignLeadStat(BaseModel):
    campaign_id: Optional[str]
    campaign_name: str
    total_leads: int
    avg_icp_score: float


class IndustryLeadStat(BaseModel):
    industry: str
    count: int


class AnalyticsLeadsResponse(BaseModel):
    total_leads: int
    by_campaign: List[CampaignLeadStat]
    by_industry: List[IndustryLeadStat]
    by_status: Dict[str, int]
