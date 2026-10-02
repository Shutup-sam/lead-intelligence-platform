import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class Lead(Base):
    """Represents an AI-qualified B2B lead derived from crawled website intelligence."""
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    crawl_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crawl_targets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    company_summary: Mapped[str] = mapped_column(Text, nullable=False)
    value_proposition: Mapped[str] = mapped_column(Text, nullable=False)
    industry: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    business_model: Mapped[str] = mapped_column(String(100), nullable=False)
    geography: Mapped[str] = mapped_column(String(100), nullable=False)
    estimated_company_size: Mapped[str] = mapped_column(String(50), nullable=False)
    technology_signals: Mapped[List[str]] = mapped_column(JSONB, nullable=False, default=list)
    
    # Qualification Scores
    icp_score: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    qualification_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    qualification_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Lead Status (NEW, REVIEW, QUALIFIED, CONTACTED, REJECTED)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="NEW", index=True
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
    organization = relationship("Organization")
    campaign = relationship("Campaign", back_populates="leads")
    signals: Mapped[List["LeadSignal"]] = relationship(
        "LeadSignal", back_populates="lead", cascade="all, delete-orphan"
    )
    embeddings: Mapped[List["LeadEmbedding"]] = relationship(
        "LeadEmbedding", back_populates="lead", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["LLMAuditLog"]] = relationship(
        "LLMAuditLog", back_populates="lead", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_leads_domain_icp", "domain", "icp_score"),
        Index("ix_leads_industry_icp", "industry", "icp_score"),
        Index("ix_leads_status_icp", "status", "icp_score"),
        Index("ix_leads_org_status", "organization_id", "status"),
        Index("ix_leads_campaign_icp", "campaign_id", "icp_score"),
    )


class LeadSignal(Base):
    """Traceable, evidence-backed qualification signal extracted from a source page."""
    __tablename__ = "lead_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    sentiment: Mapped[str] = mapped_column(String(50), nullable=False, default="positive")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="signals")


class LeadEmbedding(Base):
    """Dense vector embedding for lookalike search, retrieval, and semantic matching."""
    __tablename__ = "lead_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    embedding: Mapped[List[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="embeddings")


class LLMAuditLog(Base):
    """Telemetry and cost audit record for LLM execution."""
    __tablename__ = "llm_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="audit_logs")
