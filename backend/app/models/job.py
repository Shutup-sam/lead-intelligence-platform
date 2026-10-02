import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class JobType(str, Enum):
    CRAWL = "CRAWL"
    QUALIFY = "QUALIFY"
    CRAWL_AND_QUALIFY = "CRAWL_AND_QUALIFY"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Allowed state machine transitions
VALID_JOB_TRANSITIONS = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
}


class Job(Base):
    """Represents an asynchronous background task (crawling, qualification, or pipeline)."""
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=JobStatus.QUEUED.value, index=True
    )
    crawl_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_targets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[str] = mapped_column(String(100), nullable=False, default="queued")
    pages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    crawl_target = relationship("CrawlTarget")
    lead = relationship("Lead")
    organization = relationship("Organization")
    campaign = relationship("Campaign", back_populates="jobs")

    __table_args__ = (
        Index("ix_jobs_type_status", "job_type", "status"),
        Index("ix_jobs_target_status", "crawl_target_id", "status"),
        Index("ix_jobs_org_status", "organization_id", "status"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("status", JobStatus.QUEUED.value)
        kwargs.setdefault("progress", 0)
        kwargs.setdefault("current_stage", "queued")
        kwargs.setdefault("pages_discovered", 0)
        kwargs.setdefault("pages_crawled", 0)
        kwargs.setdefault("retry_count", 0)
        kwargs.setdefault("max_retries", 3)
        kwargs.setdefault("payload", {})
        kwargs.setdefault("result", {})
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        super().__init__(**kwargs)

    def transition_to(self, new_status: JobStatus) -> None:
        """Validates and applies a state machine transition."""
        current = JobStatus(self.status)
        if new_status not in VALID_JOB_TRANSITIONS.get(current, set()):
            raise ValueError(
                f"Invalid job state transition from {current.value} to {new_status.value}."
            )
        self.status = new_status.value
        now = datetime.now(timezone.utc)
        if new_status == JobStatus.RUNNING and not self.started_at:
            self.started_at = now
        elif new_status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            self.completed_at = now
