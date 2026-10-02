import logging
from typing import Tuple
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import require_organization_member
from app.models.organization import Organization
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsUsageResponse,
    AnalyticsLeadsResponse,
)

logger = logging.getLogger("lead_intelligence.api.analytics")

router = APIRouter(prefix="/analytics", tags=["Analytics & Usage"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_overview(
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve key metrics (total leads, qualification rate, crawls, job success, estimated AI cost) for the active organization."""
    org, _ = org_tuple
    service = AnalyticsService(db)
    return await service.get_overview(org.id)


@router.get("/usage", response_model=AnalyticsUsageResponse)
async def get_usage(
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve daily usage timeline (crawls, pages, leads, qualifications, cost) for the last 30 days."""
    org, _ = org_tuple
    service = AnalyticsService(db)
    return await service.get_usage_timeline(org.id)


@router.get("/leads", response_model=AnalyticsLeadsResponse)
async def get_leads_analytics(
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve multi-dimensional lead distribution by campaign, industry, and status."""
    org, _ = org_tuple
    service = AnalyticsService(db)
    return await service.get_leads_analytics(org.id)
