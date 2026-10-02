import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.rate_limiter import DomainRateLimiter
from app.models.job import Job, JobStatus
from app.models.crawl import CrawlTarget
from app.models.campaign import Campaign
from app.services.crawl_service import CrawlService
from app.services.lead_service import LeadService
from app.services.analytics_service import AnalyticsService
from app.schemas.campaign import CampaignICPConfig
from app.ai.models import ICPProfile
from app.workers.events import publish_job_event, JobEventType
from app.workers.retry import is_retryable_error, calculate_backoff_delay

logger = logging.getLogger("lead_intelligence.workers.jobs")


async def crawl_domain_job(ctx: Dict[str, Any], job_id_str: str) -> Dict[str, Any]:
    """
    ARQ worker task to crawl a website domain asynchronously.
    """
    logger.info("ARQ JOB RECEIVED: job_id=%s, function=crawl_domain_job", job_id_str)
    job_id = uuid.UUID(job_id_str)
    rate_limiter = DomainRateLimiter()

    async with AsyncSessionLocal() as session:
        stmt = select(Job).where(Job.id == job_id)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            logger.error("Job '%s' not found in database", job_id)
            return {"error": "Job not found"}

        # Prevent executing if already cancelled
        if job.status == JobStatus.CANCELLED.value:
            logger.info("Job '%s' was cancelled prior to worker pickup", job_id)
            return {"status": "CANCELLED"}

        # State transition: QUEUED -> RUNNING
        try:
            job.transition_to(JobStatus.RUNNING)
            job.current_stage = "initializing_crawl"
            job.progress = 10
            await session.commit()
            logger.info("JOB STATUS -> RUNNING: job_id=%s", job_id)
        except Exception as exc:
            logger.error("Failed transition to RUNNING for job %s: %s", job_id, exc)
            return {"error": str(exc)}

        payload = job.payload or {}
        url = payload.get("url") or payload.get("normalized_url")
        domain = payload.get("domain", "")
        max_pages = payload.get("max_pages", 6)

        logger.info("CRAWL STARTED: job_id=%s, domain=%s", job.id, domain)
        await publish_job_event(
            job_id=job.id,
            event_type=JobEventType.JOB_STARTED,
            stage="initializing_crawl",
            progress=10,
            message=f"Starting Scrapling crawl on {domain or url}",
            data={"domain": domain, "url": url},
        )

        # Acquire exclusive domain lock to prevent concurrent worker crawl collisions
        lock_acquired = await rate_limiter.acquire_lock(domain)
        if not lock_acquired:
            logger.warning("Could not acquire domain lock for %s; will retry later", domain)
            job.current_stage = "waiting_domain_lock"
            await session.commit()

        try:
            # Politeness delay enforcement
            await rate_limiter.wait_polite_delay(domain)

            # Emit crawl_started event
            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.CRAWL_STARTED,
                stage="crawling_pages",
                progress=25,
                message=f"Crawling root and priority pages for {domain}",
            )

            # Execute Crawl via CrawlService
            crawl_service = CrawlService(db=session)
            crawl_res = await crawl_service.execute_crawl(
                raw_url=url,
                max_pages=max_pages,
                organization_id=job.organization_id,
                campaign_id=job.campaign_id,
            )

            # Update job statistics
            job.pages_discovered = crawl_res.pages_discovered
            job.pages_crawled = crawl_res.pages_crawled
            if crawl_res.target_id:
                job.crawl_target_id = uuid.UUID(crawl_res.target_id)

            if crawl_res.status == "failed" or crawl_res.status == "ssrf_rejected":
                raise ValueError(crawl_res.error_message or f"Crawl failed with status: {crawl_res.status}")

            job.current_stage = "crawl_completed"
            job.progress = 100
            job.result = {
                "domain": crawl_res.domain,
                "target_id": crawl_res.target_id,
                "pages_crawled": crawl_res.pages_crawled,
                "pages_discovered": crawl_res.pages_discovered,
                "duration_seconds": crawl_res.duration_seconds,
            }
            job.transition_to(JobStatus.COMPLETED)
            await session.commit()

            if job.organization_id:
                analytics = AnalyticsService(db=session)
                await analytics.record_usage(
                    organization_id=job.organization_id,
                    crawls=1,
                    pages_crawled=crawl_res.pages_crawled,
                    jobs_completed=1,
                )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.JOB_COMPLETED,
                stage="crawl_completed",
                progress=100,
                message=f"Successfully crawled {crawl_res.pages_crawled} pages on {domain}",
                data=job.result,
            )
            return job.result

        except Exception as exc:
            logger.error("Error executing crawl job %s: %s", job_id, exc, exc_info=True)
            if is_retryable_error(exc) and job.retry_count < job.max_retries:
                job.retry_count += 1
                backoff = calculate_backoff_delay(job.retry_count)
                job.current_stage = f"retrying_after_{backoff}s"
                await session.commit()
                logger.info("Retrying job %s (attempt %d/%d) in %.1fs", job_id, job.retry_count, job.max_retries, backoff)
                await asyncio.sleep(backoff)
                # Re-raise so ARQ / runner can re-execute
                raise exc

            job.transition_to(JobStatus.FAILED)
            job.error_message = str(exc)
            job.current_stage = "failed"
            await session.commit()

            if job.organization_id:
                analytics = AnalyticsService(db=session)
                await analytics.record_usage(
                    organization_id=job.organization_id,
                    jobs_failed=1,
                )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.JOB_FAILED,
                stage="failed",
                progress=job.progress,
                message=f"Crawl job failed: {str(exc)}",
                data={"error": str(exc)},
            )
            return {"error": str(exc)}

        finally:
            await rate_limiter.release_lock(domain)


async def qualify_lead_job(ctx: Dict[str, Any], job_id_str: str) -> Dict[str, Any]:
    """
    ARQ worker task to qualify a crawled business target using the AI LLM pipeline.
    """
    logger.info("ARQ JOB RECEIVED: job_id=%s, function=qualify_lead_job", job_id_str)
    job_id = uuid.UUID(job_id_str)

    async with AsyncSessionLocal() as session:
        stmt = select(Job).where(Job.id == job_id)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            logger.error("Job '%s' not found in database", job_id)
            return {"error": "Job not found"}

        if job.status == JobStatus.CANCELLED.value:
            return {"status": "CANCELLED"}

        try:
            job.transition_to(JobStatus.RUNNING)
            job.current_stage = "initializing_qualification"
            job.progress = 15
            await session.commit()
            logger.info("JOB STATUS -> RUNNING: job_id=%s", job_id)
        except Exception as exc:
            logger.error("Failed transition to RUNNING for qualify job %s: %s", job_id, exc)
            return {"error": str(exc)}

        payload = job.payload or {}
        target_id_str = payload.get("crawl_target_id") or (str(job.crawl_target_id) if job.crawl_target_id else None)
        if not target_id_str:
            job.transition_to(JobStatus.FAILED)
            job.error_message = "Missing crawl_target_id for qualification"
            await session.commit()
            return {"error": job.error_message}

        target_id = uuid.UUID(target_id_str)
        raw_icp = payload.get("icp_profile")
        icp_profile = ICPProfile(**raw_icp) if raw_icp else None

        # Load campaign ICP if campaign_id is attached and icp_profile was not provided
        if job.campaign_id and not icp_profile:
            camp_stmt = select(Campaign).where(Campaign.id == job.campaign_id)
            camp_res = await session.execute(camp_stmt)
            camp = camp_res.scalar_one_or_none()
            if camp and camp.icp_config:
                icp_profile = ICPProfile(**CampaignICPConfig(**camp.icp_config).to_icp_profile_dict())

        await publish_job_event(
            job_id=job.id,
            event_type=JobEventType.QUALIFICATION_STARTED,
            stage="extracting_intelligence",
            progress=30,
            message="Running LLM lead qualification against ICP criteria",
        )

        try:
            lead_service = LeadService(db=session)

            # Emit stage 50%
            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.QUALIFICATION_STARTED,
                stage="evaluating_company",
                progress=50,
                message="Validating business model, firmographics, and positive/negative signals",
            )

            qualify_res = await lead_service.qualify_target(
                crawl_target_id=target_id,
                icp_profile=icp_profile,
                organization_id=job.organization_id,
                campaign_id=job.campaign_id,
            )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.EMBEDDING_STARTED,
                stage="generating_embedding",
                progress=80,
                message="Building canonical document and generating pgvector dense embedding",
            )

            # Lead completed
            job.lead_id = uuid.UUID(qualify_res.lead_id)
            job.current_stage = "qualification_completed"
            job.progress = 100
            job.result = qualify_res.model_dump()
            job.transition_to(JobStatus.COMPLETED)
            await session.commit()

            if job.organization_id:
                analytics = AnalyticsService(db=session)
                await analytics.record_usage(
                    organization_id=job.organization_id,
                    leads_created=1,
                    ai_qualifications=1,
                    embeddings_generated=1 if qualify_res.embedding_created else 0,
                    jobs_completed=1,
                    estimated_ai_cost=0.0008,
                )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.JOB_COMPLETED,
                stage="qualification_completed",
                progress=100,
                message=f"Lead qualified: {qualify_res.company_name} (ICP Score: {qualify_res.icp_score}/100)",
                data=job.result,
            )
            return job.result

        except Exception as exc:
            logger.error("Error executing qualify job %s: %s", job_id, exc, exc_info=True)
            if is_retryable_error(exc) and job.retry_count < job.max_retries:
                job.retry_count += 1
                backoff = calculate_backoff_delay(job.retry_count)
                job.current_stage = f"retrying_after_{backoff}s"
                await session.commit()
                await asyncio.sleep(backoff)
                raise exc

            job.transition_to(JobStatus.FAILED)
            job.error_message = str(exc)
            job.current_stage = "failed"
            await session.commit()

            if job.organization_id:
                analytics = AnalyticsService(db=session)
                await analytics.record_usage(
                    organization_id=job.organization_id,
                    jobs_failed=1,
                )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.JOB_FAILED,
                stage="failed",
                progress=job.progress,
                message=f"Qualification job failed: {str(exc)}",
                data={"error": str(exc)},
            )
            return {"error": str(exc)}


async def crawl_and_qualify_job(ctx: Dict[str, Any], job_id_str: str) -> Dict[str, Any]:
    """
    Combined end-to-end task: crawls domain (0–50% progress), then runs AI qualification (50–100%).
    """
    logger.info("ARQ JOB RECEIVED: job_id=%s, function=crawl_and_qualify_job", job_id_str)
    job_id = uuid.UUID(job_id_str)
    rate_limiter = DomainRateLimiter()

    async with AsyncSessionLocal() as session:
        stmt = select(Job).where(Job.id == job_id)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job or job.status == JobStatus.CANCELLED.value:
            return {"status": "CANCELLED" if job else "NOT_FOUND"}

        try:
            job.transition_to(JobStatus.RUNNING)
            job.current_stage = "starting_pipeline"
            job.progress = 5
            await session.commit()
            logger.info("JOB STATUS -> RUNNING: job_id=%s", job_id)
        except Exception as exc:
            logger.error("Failed transition to RUNNING for pipeline job %s: %s", job_id, exc)
            return {"error": str(exc)}

        payload = job.payload or {}
        url = payload.get("url") or payload.get("normalized_url")
        domain = payload.get("domain", "")
        max_pages = payload.get("max_pages", 6)
        raw_icp = payload.get("icp_profile")
        icp_profile = ICPProfile(**raw_icp) if raw_icp else None

        # Load campaign ICP if campaign_id is attached and icp_profile was not provided
        if job.campaign_id and not icp_profile:
            camp_stmt = select(Campaign).where(Campaign.id == job.campaign_id)
            camp_res = await session.execute(camp_stmt)
            camp = camp_res.scalar_one_or_none()
            if camp and camp.icp_config:
                icp_profile = ICPProfile(**CampaignICPConfig(**camp.icp_config).to_icp_profile_dict())

        await publish_job_event(
            job_id=job.id,
            event_type=JobEventType.JOB_STARTED,
            stage="starting_pipeline",
            progress=5,
            message=f"Initiating end-to-end discovery for {domain or url}",
        )

        # 1. Phase 1: Crawl
        await rate_limiter.acquire_lock(domain)
        try:
            logger.info("CRAWL STARTED: job_id=%s, domain=%s", job.id, domain)
            await rate_limiter.wait_polite_delay(domain)
            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.CRAWL_STARTED,
                stage="crawling_pages",
                progress=20,
                message=f"Crawling {domain} (up to {max_pages} pages)",
            )

            crawl_service = CrawlService(db=session)
            crawl_res = await crawl_service.execute_crawl(
                raw_url=url,
                max_pages=max_pages,
                organization_id=job.organization_id,
                campaign_id=job.campaign_id,
            )

            job.pages_discovered = crawl_res.pages_discovered
            job.pages_crawled = crawl_res.pages_crawled
            if crawl_res.target_id:
                job.crawl_target_id = uuid.UUID(crawl_res.target_id)
            job.progress = 50
            job.current_stage = "crawl_completed"
            await session.commit()

            if crawl_res.status == "failed" or crawl_res.status == "ssrf_rejected":
                raise ValueError(crawl_res.error_message or f"Crawl failed with status: {crawl_res.status}")

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.PAGE_CRAWLED,
                stage="crawl_completed",
                progress=50,
                message=f"Crawl complete ({crawl_res.pages_crawled} pages). Starting AI qualification.",
            )

            # 2. Phase 2: AI Qualification & Embedding
            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.QUALIFICATION_STARTED,
                stage="qualifying_llm",
                progress=65,
                message="Evaluating ICP fit score and extracting structured intelligence",
            )

            lead_service = LeadService(db=session)
            qualify_res = await lead_service.qualify_target(
                crawl_target_id=job.crawl_target_id,
                icp_profile=icp_profile,
                organization_id=job.organization_id,
                campaign_id=job.campaign_id,
            )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.EMBEDDING_COMPLETED,
                stage="embedding_stored",
                progress=90,
                message="Generating dense pgvector embedding and storing signals",
            )

            job.lead_id = uuid.UUID(qualify_res.lead_id)
            job.current_stage = "pipeline_completed"
            job.progress = 100
            job.result = {
                "crawl": {
                    "domain": crawl_res.domain,
                    "pages_crawled": crawl_res.pages_crawled,
                    "target_id": crawl_res.target_id,
                },
                "qualification": qualify_res.model_dump(),
            }
            job.transition_to(JobStatus.COMPLETED)
            await session.commit()

            if job.organization_id:
                analytics = AnalyticsService(db=session)
                await analytics.record_usage(
                    organization_id=job.organization_id,
                    crawls=1,
                    pages_crawled=crawl_res.pages_crawled,
                    leads_created=1,
                    ai_qualifications=1,
                    embeddings_generated=1 if qualify_res.embedding_created else 0,
                    jobs_completed=1,
                    estimated_ai_cost=0.001,
                )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.JOB_COMPLETED,
                stage="pipeline_completed",
                progress=100,
                message=f"Pipeline complete! {qualify_res.company_name} qualified (Score: {qualify_res.icp_score}/100)",
                data=job.result,
            )
            return job.result

        except Exception as exc:
            logger.error("Pipeline failure for job %s: %s", job_id, exc, exc_info=True)
            job.transition_to(JobStatus.FAILED)
            job.error_message = str(exc)
            job.current_stage = "failed"
            await session.commit()

            if job.organization_id:
                analytics = AnalyticsService(db=session)
                await analytics.record_usage(
                    organization_id=job.organization_id,
                    jobs_failed=1,
                )

            await publish_job_event(
                job_id=job.id,
                event_type=JobEventType.JOB_FAILED,
                stage="failed",
                progress=job.progress,
                message=f"Pipeline failed: {str(exc)}",
                data={"error": str(exc)},
            )
            return {"error": str(exc)}

        finally:
            await rate_limiter.release_lock(domain)
