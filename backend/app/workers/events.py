import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.core.redis_client import redis_client

logger = logging.getLogger("lead_intelligence.workers.events")


class JobEventType:
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    CRAWL_STARTED = "crawl_started"
    PAGE_DISCOVERED = "page_discovered"
    PAGE_CRAWLED = "page_crawled"
    QUALIFICATION_STARTED = "qualification_started"
    QUALIFICATION_COMPLETED = "qualification_completed"
    EMBEDDING_STARTED = "embedding_started"
    EMBEDDING_COMPLETED = "embedding_completed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"


async def publish_job_event(
    job_id: uuid.UUID | str,
    event_type: str,
    stage: str,
    progress: int,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    client = None,
) -> Dict[str, Any]:
    """
    Publishes a real-time progress event to Redis Pub/Sub channel for live SSE streaming.
    """
    status_map = {
        JobEventType.JOB_CREATED: "QUEUED",
        JobEventType.JOB_STARTED: "RUNNING",
        JobEventType.CRAWL_STARTED: "RUNNING",
        JobEventType.PAGE_DISCOVERED: "RUNNING",
        JobEventType.PAGE_CRAWLED: "RUNNING",
        JobEventType.QUALIFICATION_STARTED: "RUNNING",
        JobEventType.QUALIFICATION_COMPLETED: "RUNNING",
        JobEventType.EMBEDDING_STARTED: "RUNNING",
        JobEventType.EMBEDDING_COMPLETED: "RUNNING",
        JobEventType.JOB_COMPLETED: "COMPLETED",
        JobEventType.JOB_FAILED: "FAILED",
        JobEventType.JOB_CANCELLED: "CANCELLED",
    }
    inferred_status = (data or {}).get("status") or status_map.get(event_type, "RUNNING")

    event_payload = {
        "event_type": event_type,
        "job_id": str(job_id),
        "status": inferred_status,
        "stage": stage,
        "progress": min(max(0, progress), 100),
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data or {},
    }

    r_client = client or redis_client
    channel = f"job_events:{job_id}"
    try:
        json_data = json.dumps(event_payload)
        await r_client.publish(channel, json_data)
        logger.debug("Emitted event [%s] on %s: %s (%d%%)", event_type, channel, message, progress)
    except Exception as exc:
        logger.warning("Failed to publish event to Redis channel %s: %s", channel, exc)

    return event_payload
