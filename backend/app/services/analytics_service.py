import uuid
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.usage import OrganizationUsageDaily
from app.models.job import Job, JobStatus
from app.models.crawl import CrawlTarget, CrawledPage
from app.models.lead import Lead, LLMAuditLog
from app.models.campaign import Campaign
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsUsageResponse,
    DailyUsageItem,
    AnalyticsLeadsResponse,
    CampaignLeadStat,
    IndustryLeadStat,
)

logger = logging.getLogger("lead_intelligence.services.analytics")


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_usage_limits(self, organization_id: uuid.UUID) -> None:
        """
        Enforce organization usage limits prior to launching expensive jobs.
        Raises HTTP 429 if active jobs or monthly quotas are exceeded.
        """
        # 1. Check active jobs concurrency limit
        active_jobs_stmt = select(func.count(Job.id)).where(
            Job.organization_id == organization_id,
            Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
        )
        active_jobs_res = await self.db.execute(active_jobs_stmt)
        active_count = active_jobs_res.scalar_one() or 0

        if active_count >= settings.MAX_ACTIVE_JOBS_PER_ORG:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Active job limit reached ({active_count}/{settings.MAX_ACTIVE_JOBS_PER_ORG} concurrent jobs). Please wait for ongoing jobs to finish.",
            )

        # 2. Check 30-day crawls limit
        thirty_days_ago = date.today() - timedelta(days=30)
        crawls_stmt = select(func.sum(OrganizationUsageDaily.crawls)).where(
            OrganizationUsageDaily.organization_id == organization_id,
            OrganizationUsageDaily.date >= thirty_days_ago,
        )
        crawls_res = await self.db.execute(crawls_stmt)
        monthly_crawls = crawls_res.scalar_one() or 0

        if monthly_crawls >= settings.MAX_MONTHLY_CRAWLS_PER_ORG:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Monthly crawl quota exceeded ({monthly_crawls}/{settings.MAX_MONTHLY_CRAWLS_PER_ORG}).",
            )

    async def record_usage(
        self,
        organization_id: uuid.UUID,
        crawls: int = 0,
        pages_crawled: int = 0,
        leads_created: int = 0,
        ai_qualifications: int = 0,
        embeddings_generated: int = 0,
        jobs_completed: int = 0,
        jobs_failed: int = 0,
        estimated_ai_cost: float = 0.0,
    ) -> None:
        """Atomically increment daily usage metrics for an organization."""
        today = date.today()
        stmt = select(OrganizationUsageDaily).where(
            OrganizationUsageDaily.organization_id == organization_id,
            OrganizationUsageDaily.date == today,
        )
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            record = OrganizationUsageDaily(
                organization_id=organization_id,
                date=today,
                crawls=crawls,
                pages_crawled=pages_crawled,
                leads_created=leads_created,
                ai_qualifications=ai_qualifications,
                embeddings_generated=embeddings_generated,
                jobs_completed=jobs_completed,
                jobs_failed=jobs_failed,
                estimated_ai_cost=round(estimated_ai_cost, 4),
            )
            self.db.add(record)
        else:
            record.crawls += crawls
            record.pages_crawled += pages_crawled
            record.leads_created += leads_created
            record.ai_qualifications += ai_qualifications
            record.embeddings_generated += embeddings_generated
            record.jobs_completed += jobs_completed
            record.jobs_failed += jobs_failed
            record.estimated_ai_cost = round(record.estimated_ai_cost + estimated_ai_cost, 4)

        await self.db.commit()

    async def get_overview(self, organization_id: uuid.UUID) -> AnalyticsOverviewResponse:
        """Compute organization overview KPIs directly from database data."""
        # Leads counts
        leads_stmt = select(
            func.count(Lead.id).label("total"),
            func.count(func.nullif(Lead.icp_score < 50, True)).label("qualified"),
        ).where(Lead.organization_id == organization_id)
        leads_res = await self.db.execute(leads_stmt)
        total_leads, qualified_leads = leads_res.first() or (0, 0)
        total_leads = total_leads or 0
        qualified_leads = qualified_leads or 0
        qual_rate = round((qualified_leads / total_leads * 100.0), 1) if total_leads > 0 else 0.0

        # Crawls & Pages
        crawl_stmt = select(func.count(CrawlTarget.id)).where(
            CrawlTarget.organization_id == organization_id
        )
        total_crawls = (await self.db.execute(crawl_stmt)).scalar_one() or 0

        pages_stmt = (
            select(func.count(CrawledPage.id))
            .join(CrawlTarget, CrawledPage.crawl_target_id == CrawlTarget.id)
            .where(CrawlTarget.organization_id == organization_id)
        )
        pages_crawled = (await self.db.execute(pages_stmt)).scalar_one() or 0

        # Jobs
        jobs_stmt = select(
            func.count(func.nullif(Job.status != JobStatus.COMPLETED.value, True)),
            func.count(func.nullif(Job.status != JobStatus.FAILED.value, True)),
        ).where(Job.organization_id == organization_id)
        jobs_res = await self.db.execute(jobs_stmt)
        jobs_comp, jobs_fail = jobs_res.first() or (0, 0)

        # Estimated AI Cost from LLMAuditLogs
        cost_stmt = (
            select(
                func.sum(LLMAuditLog.input_tokens),
                func.sum(LLMAuditLog.output_tokens),
            )
            .join(Lead, LLMAuditLog.lead_id == Lead.id)
            .where(Lead.organization_id == organization_id)
        )
        cost_res = await self.db.execute(cost_stmt)
        in_tokens, out_tokens = cost_res.first() or (0, 0)
        in_tokens = in_tokens or 0
        out_tokens = out_tokens or 0
        # gpt-4o-mini pricing: $0.15 / 1M input, $0.60 / 1M output
        est_cost = round((in_tokens * 0.00000015) + (out_tokens * 0.00000060), 4)

        return AnalyticsOverviewResponse(
            total_leads=total_leads,
            qualified_leads=qualified_leads,
            qualification_rate=qual_rate,
            total_crawls=total_crawls,
            pages_crawled=pages_crawled,
            jobs_completed=jobs_comp or 0,
            jobs_failed=jobs_fail or 0,
            estimated_ai_cost=est_cost,
        )

    async def get_usage_timeline(self, organization_id: uuid.UUID) -> AnalyticsUsageResponse:
        """Fetch daily usage records for the last 30 days."""
        thirty_days_ago = date.today() - timedelta(days=30)
        stmt = (
            select(OrganizationUsageDaily)
            .where(
                OrganizationUsageDaily.organization_id == organization_id,
                OrganizationUsageDaily.date >= thirty_days_ago,
            )
            .order_by(desc(OrganizationUsageDaily.date))
        )
        res = await self.db.execute(stmt)
        records = res.scalars().all()

        items = [
            DailyUsageItem(
                date=r.date.isoformat(),
                crawls=r.crawls,
                pages_crawled=r.pages_crawled,
                leads_created=r.leads_created,
                ai_qualifications=r.ai_qualifications,
                embeddings_generated=r.embeddings_generated,
                jobs_completed=r.jobs_completed,
                jobs_failed=r.jobs_failed,
                estimated_ai_cost=r.estimated_ai_cost,
            )
            for r in records
        ]
        return AnalyticsUsageResponse(items=items)

    async def get_leads_analytics(self, organization_id: uuid.UUID) -> AnalyticsLeadsResponse:
        """Fetch multi-dimensional breakdown of leads by campaign, industry, and status."""
        total_stmt = select(func.count(Lead.id)).where(Lead.organization_id == organization_id)
        total_leads = (await self.db.execute(total_stmt)).scalar_one() or 0

        # By Campaign
        camp_stmt = (
            select(
                Campaign.id,
                Campaign.name,
                func.count(Lead.id).label("lead_count"),
                func.avg(Lead.icp_score).label("avg_score"),
            )
            .outerjoin(Lead, Lead.campaign_id == Campaign.id)
            .where(Campaign.organization_id == organization_id)
            .group_by(Campaign.id, Campaign.name)
            .order_by(desc("lead_count"))
        )
        camp_res = await self.db.execute(camp_stmt)
        by_campaign = [
            CampaignLeadStat(
                campaign_id=str(cid) if cid else None,
                campaign_name=cname,
                total_leads=lcount or 0,
                avg_icp_score=round(float(ascore), 1) if ascore else 0.0,
            )
            for cid, cname, lcount, ascore in camp_res.all()
        ]

        # By Industry
        ind_stmt = (
            select(Lead.industry, func.count(Lead.id))
            .where(Lead.organization_id == organization_id)
            .group_by(Lead.industry)
            .order_by(desc(func.count(Lead.id)))
            .limit(10)
        )
        ind_res = await self.db.execute(ind_stmt)
        by_industry = [
            IndustryLeadStat(industry=ind, count=cnt)
            for ind, cnt in ind_res.all()
        ]

        # By Status
        stat_stmt = (
            select(Lead.status, func.count(Lead.id))
            .where(Lead.organization_id == organization_id)
            .group_by(Lead.status)
        )
        stat_res = await self.db.execute(stat_stmt)
        by_status = {stat: cnt for stat, cnt in stat_res.all()}

        return AnalyticsLeadsResponse(
            total_leads=total_leads,
            by_campaign=by_campaign,
            by_industry=by_industry,
            by_status=by_status,
        )
