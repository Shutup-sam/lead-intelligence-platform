import uuid
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from app.models.job import Job, JobType, JobStatus
from app.services.job_service import JobService


@pytest.mark.asyncio
async def test_enqueue_crawl_endpoint_202(client: AsyncClient):
    job_id = uuid.uuid4()
    mock_job = Job(
        job_type=JobType.CRAWL.value,
        status=JobStatus.QUEUED.value,
    )
    mock_job.id = job_id

    with patch("app.api.v1.jobs.JobService.enqueue_crawl_job", new=AsyncMock(return_value=(mock_job, False))):
        res = await client.post(
            "/api/v1/jobs/crawl",
            json={"url": "https://example.com", "max_pages": 4},
        )
        assert res.status_code == 202
        data = res.json()
        assert data["job_id"] == str(job_id)
        assert data["job_type"] == "CRAWL"
        assert data["status"] == "QUEUED"
        assert data["reused"] is False


@pytest.mark.asyncio
async def test_enqueue_qualify_endpoint_202(client: AsyncClient):
    job_id = uuid.uuid4()
    target_id = uuid.uuid4()
    mock_job = Job(
        job_type=JobType.QUALIFY.value,
        status=JobStatus.QUEUED.value,
        crawl_target_id=target_id,
    )
    mock_job.id = job_id

    with patch("app.api.v1.jobs.JobService.enqueue_qualify_job", new=AsyncMock(return_value=(mock_job, False))):
        res = await client.post(
            "/api/v1/jobs/qualify",
            json={"crawl_target_id": str(target_id)},
        )
        assert res.status_code == 202
        data = res.json()
        assert data["job_id"] == str(job_id)
        assert data["status"] == "QUEUED"


@pytest.mark.asyncio
async def test_enqueue_pipeline_endpoint_202(client: AsyncClient):
    job_id = uuid.uuid4()
    mock_job = Job(
        job_type=JobType.CRAWL_AND_QUALIFY.value,
        status=JobStatus.QUEUED.value,
    )
    mock_job.id = job_id

    with patch("app.api.v1.jobs.JobService.enqueue_pipeline_job", new=AsyncMock(return_value=(mock_job, False))):
        res = await client.post(
            "/api/v1/jobs/pipeline",
            json={"url": "https://example.com", "max_pages": 5},
        )
        assert res.status_code == 202
        data = res.json()
        assert data["job_id"] == str(job_id)
        assert data["job_type"] == "CRAWL_AND_QUALIFY"


@pytest.mark.asyncio
async def test_get_job_status_endpoint(client: AsyncClient):
    job_id = uuid.uuid4()
    mock_job = Job(
        job_type=JobType.CRAWL.value,
        status=JobStatus.RUNNING.value,
        progress=45,
        current_stage="crawling_pages",
        pages_discovered=10,
        pages_crawled=4,
    )
    mock_job.id = job_id

    with patch("app.api.v1.jobs.JobService.get_job", new=AsyncMock(return_value=mock_job)):
        res = await client.get(f"/api/v1/jobs/{job_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(job_id)
        assert data["status"] == "RUNNING"
        assert data["progress"] == 45
        assert data["current_stage"] == "crawling_pages"
        assert data["pages_crawled"] == 4


@pytest.mark.asyncio
async def test_get_job_status_not_found(client: AsyncClient):
    job_id = uuid.uuid4()
    with patch("app.api.v1.jobs.JobService.get_job", new=AsyncMock(return_value=None)):
        res = await client.get(f"/api/v1/jobs/{job_id}")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_job_endpoint(client: AsyncClient):
    job_id = uuid.uuid4()
    mock_job = Job(
        job_type=JobType.CRAWL.value,
        status=JobStatus.CANCELLED.value,
    )
    mock_job.id = job_id

    with patch("app.api.v1.jobs.JobService.cancel_job", new=AsyncMock(return_value=mock_job)):
        res = await client.post(f"/api/v1/jobs/{job_id}/cancel")
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == str(job_id)
        assert data["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_stream_job_events_terminal_snapshot(client: AsyncClient):
    job_id = uuid.uuid4()
    mock_job = Job(
        job_type=JobType.CRAWL.value,
        status=JobStatus.COMPLETED.value,
        progress=100,
        current_stage="crawl_completed",
        pages_discovered=6,
        pages_crawled=6,
    )
    mock_job.id = job_id

    with patch("app.api.v1.jobs.JobService.get_job", new=AsyncMock(return_value=mock_job)):
        res = await client.get(f"/api/v1/jobs/{job_id}/events")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert "event: job_snapshot" in res.text
        assert "crawl_completed" in res.text
        # Verify top-level status is present in the payload
        assert '"status": "COMPLETED"' in res.text


@pytest.mark.asyncio
async def test_stream_job_events_query_param_auth(client: AsyncClient):
    """Verify that browser EventSource can authenticate using ?token=...&org_id=... query parameters."""
    from app.main import app
    from app.core.auth import get_current_user, get_current_organization, require_organization_member

    # Register user to get valid token and org
    unique_email = f"sse_user_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "Password123!",
            "full_name": "SSE Tester",
            "organization_name": "SSE Corp",
        },
    )
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    org_id = auth_data["organization"]["id"]

    # Temporarily remove dependency overrides to test actual query param authentication
    saved_user_override = app.dependency_overrides.pop(get_current_user, None)
    saved_org_override = app.dependency_overrides.pop(get_current_organization, None)
    saved_member_override = app.dependency_overrides.pop(require_organization_member, None)

    try:
        job_id = uuid.uuid4()
        mock_job = Job(
            job_type=JobType.CRAWL_AND_QUALIFY.value,
            status=JobStatus.COMPLETED.value,
            organization_id=uuid.UUID(org_id),
            progress=100,
            current_stage="pipeline_completed",
        )
        mock_job.id = job_id

        with patch("app.api.v1.jobs.JobService.get_job", new=AsyncMock(return_value=mock_job)):
            # Call without Authorization header, using query params only
            res = await client.get(f"/api/v1/jobs/{job_id}/events?token={token}&org_id={org_id}")
            assert res.status_code == 200
            assert "text/event-stream" in res.headers["content-type"]
            assert "event: job_snapshot" in res.text
            assert '"status": "COMPLETED"' in res.text
    finally:
        if saved_user_override:
            app.dependency_overrides[get_current_user] = saved_user_override
        if saved_org_override:
            app.dependency_overrides[get_current_organization] = saved_org_override
        if saved_member_override:
            app.dependency_overrides[require_organization_member] = saved_member_override


@pytest.mark.asyncio
async def test_job_service_enqueue_pipeline_calls_arq_correctly():
    """Verify that enqueue_pipeline_job calls ARQ with exact function name, explicit queue, and string ID."""
    from unittest.mock import MagicMock
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one.return_value = 0
    db.execute.return_value = mock_res

    arq_client = AsyncMock()
    service = JobService(db=db, arq_client=arq_client)

    org_id = uuid.uuid4()
    campaign_id = uuid.uuid4()

    with patch.object(service, "_find_active_job", new=AsyncMock(return_value=None)):
        job, reused = await service.enqueue_pipeline_job(
            url="https://quotes.toscrape.com",
            max_pages=3,
            organization_id=org_id,
            campaign_id=campaign_id,
        )

        assert reused is False
        assert job.status == JobStatus.QUEUED.value
        assert job.job_type == JobType.CRAWL_AND_QUALIFY.value

        # Verify ARQ enqueue call
        arq_client.enqueue_job.assert_called_once()
        args, kwargs = arq_client.enqueue_job.call_args
        assert args[0] == "crawl_and_qualify_job"
        assert args[1] == str(job.id)
        assert kwargs.get("_queue_name") == "arq:queue"

