import uuid
from datetime import datetime, date, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Integer, Float, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class OrganizationUsageDaily(Base):
    """Aggregated daily usage metrics for an Organization."""
    __tablename__ = "organization_usage_daily"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    crawls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_crawled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_qualifications: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embeddings_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_ai_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="daily_usage")

    __table_args__ = (
        UniqueConstraint("organization_id", "date", name="uq_org_usage_date"),
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("id", uuid.uuid4())
        kwargs.setdefault("crawls", 0)
        kwargs.setdefault("pages_crawled", 0)
        kwargs.setdefault("leads_created", 0)
        kwargs.setdefault("ai_qualifications", 0)
        kwargs.setdefault("embeddings_generated", 0)
        kwargs.setdefault("jobs_completed", 0)
        kwargs.setdefault("jobs_failed", 0)
        kwargs.setdefault("estimated_ai_cost", 0.0)
        kwargs.setdefault("created_at", datetime.now(timezone.utc))
        kwargs.setdefault("updated_at", datetime.now(timezone.utc))
        super().__init__(**kwargs)
