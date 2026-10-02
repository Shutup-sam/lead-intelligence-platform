import logging
from typing import Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth import require_organization_member
from app.models.organization import Organization
from app.crawler.models import CrawlRequest, CrawlSummaryResult
from app.services.crawl_service import CrawlService

logger = logging.getLogger("lead_intelligence.api.v1.crawl")

router = APIRouter(tags=["Crawler"])


@router.post(
    "/crawl",
    response_model=CrawlSummaryResult,
    status_code=status.HTTP_200_OK,
    summary="Crawl a permitted public business domain",
    description="Validates target domain, verifies SSRF boundaries and robots.txt, and crawls pages using Scrapling.",
)
async def crawl_website(
    payload: CrawlRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> CrawlSummaryResult:
    org, _ = org_tuple
    service = CrawlService(db=db)

    result = await service.execute_crawl(
        raw_url=payload.url,
        max_pages=payload.max_pages,
        max_depth=payload.max_depth,
        delay_seconds=payload.delay_seconds,
        timeout_seconds=payload.timeout_seconds,
        organization_id=org.id,
    )

    if result.status == "ssrf_rejected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error_message or "URL rejected by security boundary",
        )

    if result.status == "failed" and "Invalid URL" in (result.error_message or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error_message,
        )

    return result
