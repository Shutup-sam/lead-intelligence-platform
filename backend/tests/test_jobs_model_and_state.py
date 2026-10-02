import uuid
import pytest
from datetime import datetime, timezone
from app.models.job import Job, JobType, JobStatus, VALID_JOB_TRANSITIONS


def test_job_model_creation():
    job = Job(
        job_type=JobType.CRAWL.value,
        status=JobStatus.QUEUED.value,
        payload={"url": "https://example.com"},
    )
    assert job.status == "QUEUED"
    assert job.progress == 0
    assert job.current_stage == "queued"
    assert job.retry_count == 0
    assert job.max_retries == 3
    assert job.pages_crawled == 0
    assert job.pages_discovered == 0
    assert job.payload == {"url": "https://example.com"}
    assert job.result == {}


def test_job_state_machine_valid_transitions():
    job = Job(job_type=JobType.CRAWL.value, status=JobStatus.QUEUED.value)

    # QUEUED -> RUNNING
    job.transition_to(JobStatus.RUNNING)
    assert job.status == JobStatus.RUNNING.value
    assert job.started_at is not None

    # RUNNING -> COMPLETED
    job.transition_to(JobStatus.COMPLETED)
    assert job.status == JobStatus.COMPLETED.value
    assert job.completed_at is not None


def test_job_state_machine_cancellation_from_queued():
    job = Job(job_type=JobType.CRAWL.value, status=JobStatus.QUEUED.value)
    job.transition_to(JobStatus.CANCELLED)
    assert job.status == JobStatus.CANCELLED.value
    assert job.completed_at is not None


def test_job_state_machine_cancellation_from_running():
    job = Job(job_type=JobType.QUALIFY.value, status=JobStatus.QUEUED.value)
    job.transition_to(JobStatus.RUNNING)
    job.transition_to(JobStatus.CANCELLED)
    assert job.status == JobStatus.CANCELLED.value


def test_job_state_machine_failure():
    job = Job(job_type=JobType.CRAWL.value, status=JobStatus.QUEUED.value)
    job.transition_to(JobStatus.RUNNING)
    job.transition_to(JobStatus.FAILED)
    assert job.status == JobStatus.FAILED.value
    assert job.completed_at is not None


def test_job_state_machine_invalid_transitions():
    # Terminal COMPLETED cannot transition
    completed_job = Job(job_type=JobType.CRAWL.value, status=JobStatus.COMPLETED.value)
    with pytest.raises(ValueError, match="Invalid job state transition"):
        completed_job.transition_to(JobStatus.RUNNING)

    with pytest.raises(ValueError, match="Invalid job state transition"):
        completed_job.transition_to(JobStatus.QUEUED)

    # Terminal FAILED cannot transition
    failed_job = Job(job_type=JobType.CRAWL.value, status=JobStatus.FAILED.value)
    with pytest.raises(ValueError, match="Invalid job state transition"):
        failed_job.transition_to(JobStatus.COMPLETED)

    # Terminal CANCELLED cannot transition
    cancelled_job = Job(job_type=JobType.CRAWL.value, status=JobStatus.CANCELLED.value)
    with pytest.raises(ValueError, match="Invalid job state transition"):
        cancelled_job.transition_to(JobStatus.RUNNING)

    # QUEUED cannot jump directly to COMPLETED
    queued_job = Job(job_type=JobType.CRAWL.value, status=JobStatus.QUEUED.value)
    with pytest.raises(ValueError, match="Invalid job state transition"):
        queued_job.transition_to(JobStatus.COMPLETED)
