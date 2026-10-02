import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth import require_organization_member
from app.models.organization import Organization
from app.core.redis_client import redis_client
from app.models.job import JobStatus
from app.services.job_service import JobService
from app.schemas.job import (
    JobEnqueueCrawlRequest,
    JobEnqueueQualifyRequest,
    JobEnqueuePipelineRequest,
    JobEnqueueResponse,
    JobStatusResponse,
    JobCancelResponse,
)

logger = logging.getLogger("lead_intelligence.api.v1.jobs")

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "/crawl",
    response_model=JobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue asynchronous website crawl job",
    description="Validates target URL and dispatches crawl task to background ARQ worker queue. Returns 202 Accepted.",
)
async def enqueue_crawl_job(
    payload: JobEnqueueCrawlRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> JobEnqueueResponse:
    org, _ = org_tuple
    service = JobService(db=db)
    try:
        job, reused = await service.enqueue_crawl_job(
            url=payload.url,
            max_pages=payload.max_pages,
            organization_id=org.id,
            campaign_id=payload.campaign_id,
            force=payload.force,
        )
        return JobEnqueueResponse(
            job_id=str(job.id),
            job_type=job.job_type,
            status=job.status,
            reused=reused,
            message="Existing active crawl job returned" if reused else "Crawl job accepted and queued for worker execution",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to enqueue crawl job for %s: %s", payload.url, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not enqueue crawl job: {str(exc)}",
        )


@router.post(
    "/qualify",
    response_model=JobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue asynchronous AI lead qualification job",
    description="Dispatches LLM qualification and pgvector embedding generation to background worker. Returns 202 Accepted.",
)
async def enqueue_qualify_job(
    payload: JobEnqueueQualifyRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> JobEnqueueResponse:
    org, _ = org_tuple
    service = JobService(db=db)
    try:
        raw_icp = payload.icp_profile.model_dump() if payload.icp_profile else None
        job, reused = await service.enqueue_qualify_job(
            crawl_target_id=payload.crawl_target_id,
            icp_profile=raw_icp,
            organization_id=org.id,
            campaign_id=payload.campaign_id,
            force=payload.force,
        )
        return JobEnqueueResponse(
            job_id=str(job.id),
            job_type=job.job_type,
            status=job.status,
            reused=reused,
            message="Existing active qualification job returned" if reused else "Lead qualification job accepted and queued",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to enqueue qualify job for target %s: %s", payload.crawl_target_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not enqueue qualification job: {str(exc)}",
        )


@router.post(
    "/pipeline",
    response_model=JobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue end-to-end crawl + qualification pipeline job",
    description="Executes website crawl followed immediately by AI lead qualification and vector embedding in a single async job. Returns 202 Accepted.",
)
async def enqueue_pipeline_job(
    payload: JobEnqueuePipelineRequest,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> JobEnqueueResponse:
    org, _ = org_tuple
    service = JobService(db=db)
    try:
        raw_icp = payload.icp_profile.model_dump() if payload.icp_profile else None
        job, reused = await service.enqueue_pipeline_job(
            url=payload.url,
            max_pages=payload.max_pages,
            icp_profile=raw_icp,
            organization_id=org.id,
            campaign_id=payload.campaign_id,
            force=payload.force,
        )
        return JobEnqueueResponse(
            job_id=str(job.id),
            job_type=job.job_type,
            status=job.status,
            reused=reused,
            message="Existing active pipeline job returned" if reused else "End-to-end lead discovery pipeline accepted and queued",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to enqueue pipeline job for %s: %s", payload.url, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not enqueue pipeline job: {str(exc)}",
        )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job execution status and progress",
    description="Polls current stage, progress percentage, error messages, and output result for a job scoped to the active organization.",
)
async def get_job_status(
    job_id: uuid.UUID,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    org, _ = org_tuple
    service = JobService(db=db)
    job = await service.get_job(job_id, organization_id=org.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    return JobStatusResponse(
        id=str(job.id),
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        pages_discovered=job.pages_discovered,
        pages_crawled=job.pages_crawled,
        organization_id=str(job.organization_id) if job.organization_id else None,
        campaign_id=str(job.campaign_id) if job.campaign_id else None,
        crawl_target_id=str(job.crawl_target_id) if job.crawl_target_id else None,
        lead_id=str(job.lead_id) if job.lead_id else None,
        error_message=job.error_message,
        retry_count=job.retry_count,
        payload=job.payload or {},
        result=job.result or {},
        created_at=job.created_at.isoformat() if job.created_at else datetime.now(timezone.utc).isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=JobCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a queued or running job",
    description="Transitions job status to CANCELLED and halts further processing.",
)
async def cancel_job(
    job_id: uuid.UUID,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
) -> JobCancelResponse:
    org, _ = org_tuple
    service = JobService(db=db)
    try:
        job = await service.cancel_job(job_id, organization_id=org.id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID '{job_id}' not found.",
            )
        return JobCancelResponse(
            job_id=str(job.id),
            status=job.status,
            message="Job successfully cancelled.",
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get(
    "/{job_id}/events",
    summary="Server-Sent Events (SSE) live progress stream",
    description="Streams real-time execution events, progress percentages, and stage transitions directly from Redis Pub/Sub.",
)
async def stream_job_events(
    job_id: uuid.UUID,
    request: Request,
    org_tuple: Tuple[Organization, str] = Depends(require_organization_member),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_tuple
    service = JobService(db=db)
    job = await service.get_job(job_id, organization_id=org.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    async def event_generator():
        # 1. Immediate snapshot emission for client hydration / reconnection
        snapshot = {
            "event_type": "job_snapshot",
            "job_id": str(job.id),
            "status": job.status,
            "stage": job.current_stage,
            "progress": job.progress,
            "pages_discovered": job.pages_discovered,
            "pages_crawled": job.pages_crawled,
            "message": f"Job {job.id} currently in stage: {job.current_stage}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "status": job.status,
                "error_message": job.error_message,
                "result": job.result,
                "lead_id": str(job.lead_id) if job.lead_id else None,
            },
        }
        yield f"event: job_snapshot\ndata: {json.dumps(snapshot)}\n\n"

        # If job is already in a terminal state, terminate stream immediately
        if job.status in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
            return

        # 2. Subscribe to Redis Pub/Sub channel for live worker events
        channel_name = f"job_events:{job_id}"
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel_name)

        try:
            while True:
                if await request.is_disconnected():
                    logger.info("Client disconnected from SSE stream for job %s", job_id)
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    raw_data = message["data"]
                    if isinstance(raw_data, bytes):
                        raw_data = raw_data.decode("utf-8")

                    # Check if event signaled completion/failure to close stream cleanly
                    try:
                        parsed = json.loads(raw_data)
                        ev_type = parsed.get("event_type", "job_event")
                        yield f"event: {ev_type}\ndata: {raw_data}\n\n"
                        if ev_type in {"job_completed", "job_failed", "job_cancelled"}:
                            logger.info("Terminal event %s reached for job %s; closing SSE stream", ev_type, job_id)
                            break
                    except Exception:
                        yield f"data: {raw_data}\n\n"
                else:
                    # Keepalive comment to prevent proxy timeouts
                    yield ":keepalive\n\n"

        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
