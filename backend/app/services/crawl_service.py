import logging
import time
from typing import Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.config import settings
from app.models.crawl import CrawlTarget, CrawledPage
from app.crawler.models import CrawlSummaryResult, CrawlPageResult
from app.crawler.policies import normalize_url, validate_ssrf_boundary, extract_domain
from app.crawler.robots import RobotsPolicy
from app.crawler.fetcher import ScraplingFetcher
from app.crawler.crawler import WebsiteCrawler

logger = logging.getLogger("lead_intelligence.services.crawl")


class CrawlService:
    """
    Coordinates end-to-end domain discovery and crawling:
    URL normalization -> SSRF safety validation -> robots.txt evaluation ->
    polite crawling -> HTML cleaning -> metadata extraction -> DB persistence.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_crawl(
        self,
        raw_url: str,
        max_pages: Optional[int] = None,
        max_depth: Optional[int] = None,
        delay_seconds: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
        organization_id: Optional[any] = None,
        campaign_id: Optional[any] = None,
    ) -> CrawlSummaryResult:
        start_time = time.perf_counter()

        # 1. Normalize target URL
        try:
            normalized_url = normalize_url(raw_url)
            domain = extract_domain(normalized_url)
        except Exception as exc:
            logger.warning("Invalid URL supplied '%s': %s", raw_url, exc)
            return CrawlSummaryResult(
                target_url=raw_url,
                normalized_url=raw_url,
                domain="",
                status="failed",
                error_message=f"Invalid URL: {str(exc)}",
            )

        # 2. Validate SSRF boundary
        is_safe, ssrf_error = validate_ssrf_boundary(normalized_url)
        if not is_safe:
            logger.warning("SSRF boundary triggered for %s: %s", normalized_url, ssrf_error)
            return CrawlSummaryResult(
                target_url=raw_url,
                normalized_url=normalized_url,
                domain=domain,
                status="ssrf_rejected",
                error_message=f"SSRF Protection: {ssrf_error}",
            )

        # 3. Create or find existing CrawlTarget record
        target_stmt = select(CrawlTarget).where(CrawlTarget.normalized_url == normalized_url)
        if organization_id:
            target_stmt = target_stmt.where(
                or_(CrawlTarget.organization_id == organization_id, CrawlTarget.organization_id.is_(None))
            )
        res = await self.db.execute(target_stmt)
        target = res.scalar_one_or_none()

        if not target:
            target = CrawlTarget(
                url=raw_url,
                normalized_url=normalized_url,
                domain=domain,
                status="in_progress",
                organization_id=organization_id,
                campaign_id=campaign_id,
            )
            self.db.add(target)
            await self.db.flush()
        else:
            target.status = "in_progress"
            target.error_message = None
            if organization_id and not target.organization_id:
                target.organization_id = organization_id
            if campaign_id:
                target.campaign_id = campaign_id
            await self.db.flush()

        # 4. Check Robots.txt
        robots_policy = RobotsPolicy(user_agent=settings.CRAWLER_USER_AGENT)
        await robots_policy.fetch_and_parse(normalized_url, timeout=timeout_seconds or settings.CRAWLER_REQUEST_TIMEOUT)

        is_allowed, robot_reason = robots_policy.is_allowed(normalized_url)
        if not is_allowed:
            target.status = "blocked_by_robots"
            target.error_message = robot_reason
            await self.db.commit()
            duration = round(time.perf_counter() - start_time, 2)
            return CrawlSummaryResult(
                target_id=str(target.id),
                target_url=raw_url,
                normalized_url=normalized_url,
                domain=domain,
                status="blocked_by_robots",
                robots_status=robot_reason,
                duration_seconds=duration,
                error_message=robot_reason,
            )

        # 5. Configure Fetcher & Crawler
        fetcher = ScraplingFetcher(
            timeout=timeout_seconds or settings.CRAWLER_REQUEST_TIMEOUT,
            delay_seconds=delay_seconds if delay_seconds is not None else settings.CRAWLER_DELAY_SECONDS,
            max_retries=settings.CRAWLER_MAX_RETRIES,
            user_agent=settings.CRAWLER_USER_AGENT,
        )

        crawler = WebsiteCrawler(
            fetcher=fetcher,
            robots_policy=robots_policy,
            max_pages=max_pages or settings.CRAWLER_MAX_PAGES,
            max_depth=max_depth if max_depth is not None else settings.CRAWLER_MAX_DEPTH,
        )

        # 6. Execute Crawl
        try:
            crawled_pages, total_discovered, total_failed = await crawler.crawl_site(normalized_url)
        except Exception as exc:
            logger.error("Crawl execution error on %s: %s", normalized_url, exc, exc_info=True)
            target.status = "failed"
            target.error_message = str(exc)
            await self.db.commit()
            duration = round(time.perf_counter() - start_time, 2)
            return CrawlSummaryResult(
                target_id=str(target.id),
                target_url=raw_url,
                normalized_url=normalized_url,
                domain=domain,
                status="failed",
                error_message=str(exc),
                duration_seconds=duration,
            )

        # 7. Persist Crawled Pages
        all_emails: Set[str] = set()
        all_phones: Set[str] = set()

        for p in crawled_pages:
            all_emails.update(p.emails)
            all_phones.update(p.phones)

            db_page = CrawledPage(
                crawl_target_id=target.id,
                url=p.url,
                final_url=p.final_url,
                depth=p.depth,
                status_code=p.status_code,
                title=p.title,
                content_markdown=p.content_markdown,
                content_hash=p.content_hash,
                page_metadata={
                    "description": p.description,
                    "canonical_url": p.canonical_url,
                    "language": p.language,
                    "emails": p.emails,
                    "phones": p.phones,
                    "addresses": p.addresses,
                    "internal_links": p.internal_links,
                    "external_links": p.external_links,
                    "social_links": p.social_links,
                    "json_ld": p.json_ld,
                    "open_graph": p.open_graph,
                },
                response_time_ms=p.response_time_ms,
                fetched_at=p.fetched_at,
            )
            self.db.add(db_page)

        # 8. Finalize Target Status
        target.status = "completed" if crawled_pages else "failed"
        if not crawled_pages and total_failed > 0:
            target.error_message = f"Failed to retrieve pages from {domain}"

        await self.db.commit()

        duration = round(time.perf_counter() - start_time, 2)

        return CrawlSummaryResult(
            target_id=str(target.id),
            target_url=raw_url,
            normalized_url=normalized_url,
            domain=domain,
            status=target.status,
            pages_discovered=total_discovered,
            pages_crawled=len(crawled_pages),
            pages_failed=total_failed,
            emails_found=len(all_emails),
            phones_found=len(all_phones),
            duration_seconds=duration,
            robots_status="allowed",
            crawled_pages=crawled_pages,
        )
