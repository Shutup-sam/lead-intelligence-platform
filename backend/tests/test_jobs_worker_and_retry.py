import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.workers.retry import is_retryable_error, calculate_backoff_delay
from app.core.rate_limiter import DomainRateLimiter
from app.workers.events import publish_job_event, JobEventType
from app.models.job import Job, JobType, JobStatus
from app.services.job_service import JobService
from app.workers.jobs import crawl_domain_job, qualify_lead_job


def test_retry_classification():
    # Transient / retryable
    assert is_retryable_error(TimeoutError("Operation timed out")) is True
    assert is_retryable_error(ConnectionError("Connection refused by server")) is True
    assert is_retryable_error(Exception("HTTP 502 Bad Gateway")) is True
    assert is_retryable_error(Exception("Rate limit 429 exceeded")) is True

    # Permanent / non-retryable
    assert is_retryable_error(ValueError("Invalid URL: must start with http")) is False
    assert is_retryable_error(ValueError("SSRF Protection: target IP is private")) is False
    assert is_retryable_error(ValueError("Unsupported scheme ftp://")) is False
    assert is_retryable_error(Exception("Target blocked_by_robots")) is False


def test_backoff_calculation():
    # retry_count 0 -> base_delay ~ 1.0s + jitter
    delay_0 = calculate_backoff_delay(0, base_delay=1.0, max_delay=30.0, jitter=0.5)
    assert 1.0 <= delay_0 <= 1.5

    # retry_count 2 -> base_delay * 4 ~ 4.0s + jitter
    delay_2 = calculate_backoff_delay(2, base_delay=1.0, max_delay=30.0, jitter=0.5)
    assert 4.0 <= delay_2 <= 4.5

    # Caps at max_delay
    delay_large = calculate_backoff_delay(10, base_delay=1.0, max_delay=20.0, jitter=0.5)
    assert delay_large == 20.0


@pytest.mark.asyncio
async def test_domain_rate_limiter_lock():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True  # Lock acquired
    limiter = DomainRateLimiter(client=mock_redis)

    acquired = await limiter.acquire_lock("example.com", timeout_seconds=60)
    assert acquired is True
    mock_redis.set.assert_called_once_with("crawler:lock:example.com", "locked", nx=True, ex=60)

    # Release
    await limiter.release_lock("example.com")
    mock_redis.delete.assert_called_once_with("crawler:lock:example.com")


@pytest.mark.asyncio
async def test_domain_rate_limiter_lock_denied():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = False  # Lock already held
    limiter = DomainRateLimiter(client=mock_redis)

    acquired = await limiter.acquire_lock("locked-domain.com")
    assert acquired is False


@pytest.mark.asyncio
async def test_publish_job_event():
    mock_redis = AsyncMock()
    job_id = uuid.uuid4()

    event = await publish_job_event(
        job_id=job_id,
        event_type=JobEventType.PAGE_CRAWLED,
        stage="crawling_pages",
        progress=45,
        message="Crawled 3 pages",
        data={"pages": 3},
        client=mock_redis,
    )

    assert event["event_type"] == "page_crawled"
    assert event["progress"] == 45
    assert event["stage"] == "crawling_pages"
    mock_redis.publish.assert_called_once()
    channel = mock_redis.publish.call_args[0][0]
    assert channel == f"job_events:{job_id}"


@pytest.mark.asyncio
async def test_job_service_idempotency_reuse():
    db = AsyncMock()
    arq_client = AsyncMock()
    service = JobService(db=db, arq_client=arq_client)

    active_job = Job(
        job_type=JobType.CRAWL.value,
        status=JobStatus.RUNNING.value,
        idempotency_key="crawl:https://example.com/",
    )

    with patch.object(service, "_find_active_job", new=AsyncMock(return_value=active_job)):
        job, reused = await service.enqueue_crawl_job("https://example.com", force=False)
        assert reused is True
        assert job == active_job
        # Arq pool should not have been called for reused active job
        arq_client.enqueue_job.assert_not_called()
