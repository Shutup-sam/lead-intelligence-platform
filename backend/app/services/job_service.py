import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

from app.core.config import settings
from app.models.job import Job, JobType, JobStatus
from app.crawler.policies import normalize_url, extract_domain
from app.workers.events import publish_job_event, JobEventType
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger("lead_intelligence.services.job")

_arq_pool: Optional[ArqRedis] = None


async def get_arq_pool() -> ArqRedis:
    """Provides a shared connection pool to the ARQ Redis job queue."""
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _arq_pool


async def close_arq_pool() -> None:
    """Closes ARQ pool on application shutdown."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None


JOB_ARQ_FUNCTIONS = {
    JobType.CRAWL: "crawl_domain_job",
    JobType.QUALIFY: "qualify_lead_job",
    JobType.CRAWL_AND_QUALIFY: "crawl_and_qualify_job",
}


class JobService:
    """
    Manages persistent jobs in PostgreSQL, state transitions,
    idempotency enforcement, event emission, and ARQ queue dispatch.
    """

    def __init__(self, db: AsyncSession, arq_client: Optional[ArqRedis] = None):
        self.db = db
        self.arq_client = arq_client

    async def _get_arq_client(self) -> ArqRedis:
        if self.arq_client:
            return self.arq_client
        return await get_arq_pool()

    async def enqueue_crawl_job(
        self,
        url: str,
        max_pages: int = 6,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
        force: bool = False,
    ) -> Tuple[Job, bool]:
        """
        Enqueues an asynchronous crawl job with deterministic idempotency.
        Returns (job, reused).
        """
        if organization_id:
            analytics = AnalyticsService(self.db)
            await analytics.check_usage_limits(organization_id)

        norm_url = normalize_url(url)
        domain = extract_domain(norm_url)
        idempotency_key = f"crawl:{organization_id}:{norm_url}" if organization_id else f"crawl:{norm_url}"

        # Check for existing active job
        if not force:
            active_job = await self._find_active_job(idempotency_key)
            if active_job:
                logger.info("Reusing active crawl job '%s' for '%s'", active_job.id, norm_url)
                return active_job, True

        # Create new job
        job = Job(
            job_type=JobType.CRAWL.value,
            status=JobStatus.QUEUED.value,
            organization_id=organization_id,
            campaign_id=campaign_id,
            current_stage="queued",
            progress=0,
            idempotency_key=idempotency_key,
            payload={"url": url, "normalized_url": norm_url, "domain": domain, "max_pages": max_pages},
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        # Emit created event
        await publish_job_event(
            job_id=job.id,
            event_type=JobEventType.JOB_CREATED,
            stage="queued",
            progress=0,
            message=f"Crawl job queued for {domain}",
            data={"domain": domain, "url": norm_url},
        )

        # Dispatch to ARQ
        logger.info(
            "JOB CREATE: job_id=%s, job_type=%s, redis_url=%s, queue_name=%s, arq_function=crawl_domain_job",
            job.id, job.job_type, settings.REDIS_URL, settings.ARQ_QUEUE_NAME
        )
        logger.info("ARQ ENQUEUE START: job_id=%s, arq_function=crawl_domain_job", job.id)
        try:
            pool = await self._get_arq_client()
            await pool.enqueue_job("crawl_domain_job", str(job.id), _queue_name=settings.ARQ_QUEUE_NAME)
            logger.info("ARQ ENQUEUE SUCCESS: job_id=%s, arq_function=crawl_domain_job", job.id)
        except Exception as exc:
            logger.error("ARQ ENQUEUE FAILED: job_id=%s, arq_function=crawl_domain_job, error=%s", job.id, exc)
            raise

        return job, False

    async def enqueue_qualify_job(
        self,
        crawl_target_id: uuid.UUID,
        icp_profile: Optional[Dict[str, Any]] = None,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
        force: bool = False,
    ) -> Tuple[Job, bool]:
        """
        Enqueues an asynchronous lead qualification job.
        Returns (job, reused).
        """
        if organization_id:
            analytics = AnalyticsService(self.db)
            await analytics.check_usage_limits(organization_id)

        idempotency_key = f"qualify:{organization_id}:{crawl_target_id}" if organization_id else f"qualify:{crawl_target_id}"

        if not force:
            active_job = await self._find_active_job(idempotency_key)
            if active_job:
                logger.info("Reusing active qualify job '%s' for target '%s'", active_job.id, crawl_target_id)
                return active_job, True

        job = Job(
            job_type=JobType.QUALIFY.value,
            status=JobStatus.QUEUED.value,
            organization_id=organization_id,
            campaign_id=campaign_id,
            crawl_target_id=crawl_target_id,
            current_stage="queued",
            progress=0,
            idempotency_key=idempotency_key,
            payload={"crawl_target_id": str(crawl_target_id), "icp_profile": icp_profile or {}},
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        await publish_job_event(
            job_id=job.id,
            event_type=JobEventType.JOB_CREATED,
            stage="queued",
            progress=0,
            message="Lead qualification job queued",
            data={"crawl_target_id": str(crawl_target_id)},
        )

        logger.info(
            "JOB CREATE: job_id=%s, job_type=%s, redis_url=%s, queue_name=%s, arq_function=qualify_lead_job",
            job.id, job.job_type, settings.REDIS_URL, settings.ARQ_QUEUE_NAME
        )
        logger.info("ARQ ENQUEUE START: job_id=%s, arq_function=qualify_lead_job", job.id)
        try:
            pool = await self._get_arq_client()
            await pool.enqueue_job("qualify_lead_job", str(job.id), _queue_name=settings.ARQ_QUEUE_NAME)
            logger.info("ARQ ENQUEUE SUCCESS: job_id=%s, arq_function=qualify_lead_job", job.id)
        except Exception as exc:
            logger.error("ARQ ENQUEUE FAILED: job_id=%s, arq_function=qualify_lead_job, error=%s", job.id, exc)
            raise

        return job, False

    async def enqueue_pipeline_job(
        self,
        url: str,
        max_pages: int = 6,
        icp_profile: Optional[Dict[str, Any]] = None,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
        force: bool = False,
    ) -> Tuple[Job, bool]:
        """
        Enqueues combined crawl + AI qualification end-to-end pipeline job.
        Returns (job, reused).
        """
        if organization_id:
            analytics = AnalyticsService(self.db)
            await analytics.check_usage_limits(organization_id)

        norm_url = normalize_url(url)
        domain = extract_domain(norm_url)
        idempotency_key = f"pipeline:{organization_id}:{norm_url}" if organization_id else f"pipeline:{norm_url}"

        if not force:
            active_job = await self._find_active_job(idempotency_key)
            if active_job:
                logger.info("Reusing active pipeline job '%s' for '%s'", active_job.id, norm_url)
                return active_job, True

        job = Job(
            job_type=JobType.CRAWL_AND_QUALIFY.value,
            status=JobStatus.QUEUED.value,
            organization_id=organization_id,
            campaign_id=campaign_id,
            current_stage="queued",
            progress=0,
            idempotency_key=idempotency_key,
            payload={
                "url": url,
                "normalized_url": norm_url,
                "domain": domain,
                "max_pages": max_pages,
                "icp_profile": icp_profile or {},
            },
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        await publish_job_event(
            job_id=job.id,
            event_type=JobEventType.JOB_CREATED,
            stage="queued",
            progress=0,
            message=f"End-to-end intelligence pipeline queued for {domain}",
            data={"domain": domain, "url": norm_url},
        )

        logger.info(
            "JOB CREATE: job_id=%s, job_type=%s, redis_url=%s, queue_name=%s, arq_function=crawl_and_qualify_job",
            job.id, job.job_type, settings.REDIS_URL, settings.ARQ_QUEUE_NAME
        )
        logger.info("ARQ ENQUEUE START: job_id=%s, arq_function=crawl_and_qualify_job", job.id)
        try:
            pool = await self._get_arq_client()
            await pool.enqueue_job("crawl_and_qualify_job", str(job.id), _queue_name=settings.ARQ_QUEUE_NAME)
            logger.info("ARQ ENQUEUE SUCCESS: job_id=%s, arq_function=crawl_and_qualify_job", job.id)
        except Exception as exc:
            logger.error("ARQ ENQUEUE FAILED: job_id=%s, arq_function=crawl_and_qualify_job, error=%s", job.id, exc)
            raise

        return job, False

    async def _find_active_job(self, idempotency_key: str) -> Optional[Job]:
        """Finds any non-terminal job matching the idempotency key."""
        stmt = select(Job).where(
            and_(
                Job.idempotency_key == idempotency_key,
                Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
            )
        ).order_by(desc(Job.created_at))
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_job(
        self, job_id: uuid.UUID, organization_id: Optional[uuid.UUID] = None
    ) -> Optional[Job]:
        """Fetches job by UUID, optionally ensuring organization ownership."""
        stmt = select(Job).where(Job.id == job_id)
        if organization_id:
            stmt = stmt.where(
                or_(Job.organization_id == organization_id, Job.organization_id.is_(None))
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def cancel_job(
        self, job_id: uuid.UUID, organization_id: Optional[uuid.UUID] = None
    ) -> Optional[Job]:
        """Requests cancellation of a queued or running job."""
        job = await self.get_job(job_id, organization_id=organization_id)
        if not job:
            return None

        job.transition_to(JobStatus.CANCELLED)
        job.current_stage = "cancelled"
        await self.db.commit()
        await self.db.refresh(job)

        await publish_job_event(
            job_id=job.id,
            event_type=JobEventType.JOB_CANCELLED,
            stage="cancelled",
            progress=job.progress,
            message="Job was cancelled by user request",
        )
        return job
