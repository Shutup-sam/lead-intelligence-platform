import csv
import io
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_, and_, desc, asc

from app.models.crawl import CrawlTarget, CrawledPage
from app.models.lead import Lead, LeadSignal, LeadEmbedding, LLMAuditLog
from app.ai.models import ICPProfile, LeadQualifyResponse, CompanyQualification, QualificationSignal
from app.ai.pipeline import QualificationPipeline
from app.ai.embeddings import (
    get_embedding_provider,
    build_canonical_embedding_document,
    compute_content_hash,
)
from app.schemas.lead import (
    LeadStatus,
    LeadListItem,
    LeadListResponse,
    SemanticSearchResultItem,
    SemanticSearchResponse,
    HybridSearchResponse,
)

logger = logging.getLogger("lead_intelligence.services.lead")


class LeadService:
    """
    Coordinates lead qualification, transactional persistence, retrieval,
    relational filtering, semantic vector search, hybrid ranking, and export.
    """

    def __init__(self, db: AsyncSession, pipeline: Optional[QualificationPipeline] = None):
        self.db = db
        self.pipeline = pipeline or QualificationPipeline()
        self.embedding_provider = get_embedding_provider()

    async def qualify_target(
        self,
        crawl_target_id: uuid.UUID,
        icp_profile: Optional[ICPProfile] = None,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
    ) -> LeadQualifyResponse:
        start_time = time.perf_counter()

        # 1. Fetch CrawlTarget
        target_stmt = select(CrawlTarget).where(CrawlTarget.id == crawl_target_id)
        if organization_id:
            target_stmt = target_stmt.where(
                or_(CrawlTarget.organization_id == organization_id, CrawlTarget.organization_id.is_(None))
            )
        target_res = await self.db.execute(target_stmt)
        target = target_res.scalar_one_or_none()
        if not target:
            raise ValueError(f"CrawlTarget with ID '{crawl_target_id}' not found.")

        # 2. Fetch CrawledPages
        pages_res = await self.db.execute(
            select(CrawledPage)
            .where(CrawledPage.crawl_target_id == crawl_target_id)
            .order_by(CrawledPage.depth.asc())
        )
        db_pages = pages_res.scalars().all()
        if not db_pages:
            raise ValueError(f"No crawled pages found for target '{target.domain}'. Please crawl domain before qualifying.")

        # Prepare page dicts for AI pipeline
        pages_data = [
            {
                "url": p.url,
                "title": p.title,
                "content_markdown": p.content_markdown,
                "content_hash": p.content_hash,
                "depth": p.depth,
                "metadata": p.page_metadata,
            }
            for p in db_pages
        ]

        # 3. Execute AI Pipeline
        qualification, canonical_doc, emb_hash, emb_vector, audit_exec = await self.pipeline.qualify(
            domain=target.domain,
            target_url=target.normalized_url,
            crawled_pages=pages_data,
            icp_profile=icp_profile,
        )

        # 4. Transactional Database Persistence
        try:
            # Check if lead already exists for this target
            lead_stmt = select(Lead).where(Lead.crawl_target_id == crawl_target_id)
            if organization_id:
                lead_stmt = lead_stmt.where(
                    or_(Lead.organization_id == organization_id, Lead.organization_id.is_(None))
                )
            lead_res = await self.db.execute(lead_stmt)
            lead = lead_res.scalar_one_or_none()

            effective_org_id = organization_id or target.organization_id
            effective_camp_id = campaign_id or target.campaign_id

            if not lead:
                lead = Lead(
                    crawl_target_id=target.id,
                    organization_id=effective_org_id,
                    campaign_id=effective_camp_id,
                    company_name=qualification.company_name,
                    domain=target.domain,
                    company_summary=qualification.company_summary,
                    value_proposition=qualification.value_proposition,
                    industry=qualification.industry,
                    target_audience=qualification.target_audience,
                    business_model=qualification.business_model,
                    geography=qualification.geography,
                    estimated_company_size=qualification.estimated_company_size,
                    technology_signals=qualification.technology_signals,
                    icp_score=qualification.icp_score,
                    confidence_score=qualification.confidence_score,
                    qualification_reasoning=qualification.qualification_reasoning,
                    qualification_json=qualification.model_dump(),
                    status=LeadStatus.NEW.value,
                )
                self.db.add(lead)
                await self.db.flush()
            else:
                # Update existing lead fields
                lead.company_name = qualification.company_name
                lead.company_summary = qualification.company_summary
                lead.value_proposition = qualification.value_proposition
                lead.industry = qualification.industry
                lead.target_audience = qualification.target_audience
                lead.business_model = qualification.business_model
                lead.geography = qualification.geography
                lead.estimated_company_size = qualification.estimated_company_size
                lead.technology_signals = qualification.technology_signals
                lead.icp_score = qualification.icp_score
                lead.confidence_score = qualification.confidence_score
                lead.qualification_reasoning = qualification.qualification_reasoning
                lead.qualification_json = qualification.model_dump()
                await self.db.flush()

                # Clean up previous signals to replace with fresh evaluation
                await self.db.execute(delete(LeadSignal).where(LeadSignal.lead_id == lead.id))

            # Insert Signals
            for sig in qualification.signals:
                lead_sig = LeadSignal(
                    lead_id=lead.id,
                    signal=sig.signal,
                    evidence=sig.evidence,
                    source_url=sig.source_url,
                    sentiment=sig.sentiment,
                )
                self.db.add(lead_sig)

            # Insert or Reuse Embedding (Idempotency check)
            emb_stmt = select(LeadEmbedding).where(LeadEmbedding.lead_id == lead.id)
            emb_res = await self.db.execute(emb_stmt)
            existing_emb = emb_res.scalar_one_or_none()

            embedding_created = False
            if not existing_emb:
                new_emb = LeadEmbedding(
                    lead_id=lead.id,
                    content=canonical_doc,
                    content_hash=emb_hash,
                    embedding=emb_vector,
                )
                self.db.add(new_emb)
                embedding_created = True
            elif existing_emb.content_hash != emb_hash:
                # Content changed: update embedding and hash
                existing_emb.content = canonical_doc
                existing_emb.content_hash = emb_hash
                existing_emb.embedding = emb_vector
                embedding_created = True
            else:
                # Content hash matches: reuse existing embedding
                logger.info("Embedding content hash '%s' unchanged; reusing existing vector", emb_hash[:8])
                embedding_created = False

            # Insert LLM Audit Log
            audit_log = LLMAuditLog(
                lead_id=lead.id,
                provider=audit_exec.provider,
                model=audit_exec.model,
                input_tokens=audit_exec.input_tokens,
                output_tokens=audit_exec.output_tokens,
                total_tokens=audit_exec.total_tokens,
                latency_ms=audit_exec.latency_ms,
                request_id=audit_exec.request_id,
            )
            self.db.add(audit_log)

            await self.db.commit()

        except Exception as exc:
            await self.db.rollback()
            logger.error("Transactional rollback during lead persistence for %s: %s", target.domain, exc, exc_info=True)
            raise

        duration_sec = round(time.perf_counter() - start_time, 2)

        return LeadQualifyResponse(
            lead_id=str(lead.id),
            company_name=lead.company_name,
            domain=lead.domain,
            icp_score=lead.icp_score,
            confidence_score=lead.confidence_score,
            signals_count=len(qualification.signals),
            embedding_created=embedding_created,
            llm_provider=audit_exec.provider,
            llm_model=audit_exec.model,
            duration_seconds=duration_sec,
        )

    def _build_filter_conditions(
        self,
        search: Optional[str] = None,
        min_icp_score: Optional[int] = None,
        max_icp_score: Optional[int] = None,
        industry: Optional[str] = None,
        geography: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
    ) -> List[Any]:
        conditions = []
        if organization_id:
            conditions.append(
                or_(Lead.organization_id == organization_id, Lead.organization_id.is_(None))
            )
        if campaign_id:
            conditions.append(Lead.campaign_id == campaign_id)
        if min_icp_score is not None:
            conditions.append(Lead.icp_score >= min_icp_score)
        if max_icp_score is not None:
            conditions.append(Lead.icp_score <= max_icp_score)
        if industry and industry.strip():
            conditions.append(Lead.industry.ilike(f"%{industry.strip()}%"))
        if geography and geography.strip():
            conditions.append(Lead.geography.ilike(f"%{geography.strip()}%"))
        if status and status.strip():
            conditions.append(Lead.status == status.strip().upper())
        if search and search.strip():
            term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Lead.company_name.ilike(term),
                    Lead.domain.ilike(term),
                    Lead.industry.ilike(term),
                    Lead.company_summary.ilike(term),
                    Lead.value_proposition.ilike(term),
                )
            )
        return conditions

    async def list_leads(
        self,
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        min_icp_score: Optional[int] = None,
        max_icp_score: Optional[int] = None,
        industry: Optional[str] = None,
        geography: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> LeadListResponse:
        """Retrieves paginated, filtered, and sorted leads scoped to an organization."""
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        conditions = self._build_filter_conditions(
            search=search,
            min_icp_score=min_icp_score,
            max_icp_score=max_icp_score,
            industry=industry,
            geography=geography,
            status=status,
            organization_id=organization_id,
            campaign_id=campaign_id,
        )

        # Count total
        count_stmt = select(func.count(Lead.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Sort order
        sort_attr = getattr(Lead, sort_by, Lead.created_at)
        order_clause = desc(sort_attr) if sort_order.lower() == "desc" else asc(sort_attr)

        # Query items
        stmt = select(Lead)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(order_clause).offset((page - 1) * page_size).limit(page_size)

        leads_res = await self.db.execute(stmt)
        leads = leads_res.scalars().all()

        items = [
            LeadListItem(
                lead_id=str(l.id),
                crawl_target_id=str(l.crawl_target_id),
                company_name=l.company_name,
                domain=l.domain,
                industry=l.industry,
                company_summary=l.company_summary,
                value_proposition=l.value_proposition,
                icp_score=l.icp_score,
                confidence_score=l.confidence_score,
                geography=l.geography,
                estimated_company_size=l.estimated_company_size,
                status=l.status,
                created_at=l.created_at.isoformat(),
            )
            for l in leads
        ]

        pages = math.ceil(total / page_size) if total > 0 else 0

        return LeadListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            pages=pages,
        )

    async def update_lead_status(
        self,
        lead_id: uuid.UUID,
        new_status: str,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Optional[Lead]:
        """Updates the workflow status of a lead, enforcing tenant isolation."""
        valid_status = getattr(LeadStatus, new_status.upper(), None)
        if not valid_status:
            raise ValueError(f"Invalid status '{new_status}'. Allowed values: {[s.value for s in LeadStatus]}")

        stmt = select(Lead).where(Lead.id == lead_id)
        if organization_id:
            stmt = stmt.where(
                or_(Lead.organization_id == organization_id, Lead.organization_id.is_(None))
            )
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            return None

        lead.status = valid_status.value
        lead.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(lead)
        return lead

    async def semantic_search(
        self,
        query: str,
        limit: int = 20,
        organization_id: Optional[uuid.UUID] = None,
    ) -> SemanticSearchResponse:
        """
        Executes dense vector semantic search against pgvector lead_embeddings scoped to an organization.
        Uses cosine distance (<=>) converted to similarity: max(0.0, 1.0 - distance).
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")

        limit = min(max(1, limit), 100)

        # 1. Embed query
        query_vector = await self.embedding_provider.generate_embedding(query.strip())

        # 2. Query pgvector cosine distance
        distance_expr = LeadEmbedding.embedding.cosine_distance(query_vector)

        stmt = (
            select(Lead, distance_expr.label("distance"))
            .join(LeadEmbedding, Lead.id == LeadEmbedding.lead_id)
        )
        if organization_id:
            stmt = stmt.where(
                or_(Lead.organization_id == organization_id, Lead.organization_id.is_(None))
            )
        stmt = stmt.order_by(distance_expr.asc()).limit(limit)

        res = await self.db.execute(stmt)
        rows = res.all()

        results: List[SemanticSearchResultItem] = []
        for lead, distance in rows:
            # Cosine distance in pgvector ranges from 0 (identical) to 2 (opposite)
            similarity = max(0.0, round(1.0 - float(distance), 4))
            results.append(
                SemanticSearchResultItem(
                    lead_id=str(lead.id),
                    company_name=lead.company_name,
                    domain=lead.domain,
                    industry=lead.industry,
                    company_summary=lead.company_summary,
                    icp_score=lead.icp_score,
                    confidence_score=lead.confidence_score,
                    geography=lead.geography,
                    status=lead.status,
                    similarity=similarity,
                )
            )

        return SemanticSearchResponse(
            query=query.strip(),
            results=results,
            count=len(results),
        )

    async def hybrid_search(
        self,
        query: Optional[str] = None,
        min_icp_score: Optional[int] = None,
        max_icp_score: Optional[int] = None,
        industry: Optional[str] = None,
        geography: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
        limit: int = 25,
    ) -> HybridSearchResponse:
        """
        Executes hybrid search combining:
        1. Relational SQL filters (ICP score range, industry, geography, status, org)
        2. Dense vector cosine similarity via pgvector (60% weight)
        3. ICP Fit Score normalized (25% weight)
        4. Textual keyword relevance (15% weight)
        """
        limit = min(max(1, limit), 100)

        conditions = self._build_filter_conditions(
            search=None,
            min_icp_score=min_icp_score,
            max_icp_score=max_icp_score,
            industry=industry,
            geography=geography,
            status=status,
            organization_id=organization_id,
            campaign_id=campaign_id,
        )

        if not query or not query.strip():
            # No query provided: fallback to relational filtering ordered by icp_score
            stmt = select(Lead)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(desc(Lead.icp_score), desc(Lead.created_at)).limit(limit)
            res = await self.db.execute(stmt)
            leads = res.scalars().all()

            results = [
                LeadListItem(
                    lead_id=str(l.id),
                    crawl_target_id=str(l.crawl_target_id),
                    company_name=l.company_name,
                    domain=l.domain,
                    industry=l.industry,
                    company_summary=l.company_summary,
                    value_proposition=l.value_proposition,
                    icp_score=l.icp_score,
                    confidence_score=l.confidence_score,
                    geography=l.geography,
                    estimated_company_size=l.estimated_company_size,
                    status=l.status,
                    created_at=l.created_at.isoformat(),
                    similarity=None,
                )
                for l in leads
            ]
            return HybridSearchResponse(
                query=None,
                results=results,
                total=len(results),
                ranking_strategy="Relational filter ranking: ICP Score (desc), Created (desc)",
            )

        # Generate query vector
        clean_query = query.strip()
        query_vector = await self.embedding_provider.generate_embedding(clean_query)
        distance_expr = LeadEmbedding.embedding.cosine_distance(query_vector)

        stmt = (
            select(Lead, distance_expr.label("distance"))
            .join(LeadEmbedding, Lead.id == LeadEmbedding.lead_id)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Fetch top candidate rows
        stmt = stmt.order_by(distance_expr.asc()).limit(limit * 2)
        res = await self.db.execute(stmt)
        candidates = res.all()

        scored_items: List[Tuple[float, float, Lead]] = []
        terms = [t.lower() for t in clean_query.split() if len(t) > 2]

        for lead, distance in candidates:
            # Semantic similarity (0.0 to 1.0)
            similarity = max(0.0, 1.0 - float(distance))

            # ICP score normalized (0.0 to 1.0)
            icp_norm = float(lead.icp_score) / 100.0

            # Textual match score (0.0 to 1.0)
            text_haystack = f"{lead.company_name} {lead.industry} {lead.company_summary} {lead.value_proposition}".lower()
            text_matches = sum(1 for term in terms if term in text_haystack) if terms else 0
            text_score = min(1.0, text_matches / len(terms)) if terms else 0.0

            # Blended rank score: 60% semantic + 25% ICP fit + 15% text keyword match
            blended_score = round(0.60 * similarity + 0.25 * icp_norm + 0.15 * text_score, 4)
            scored_items.append((blended_score, similarity, lead))

        # Sort by blended score descending
        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_items = scored_items[:limit]

        results = [
            LeadListItem(
                lead_id=str(lead.id),
                crawl_target_id=str(lead.crawl_target_id),
                company_name=lead.company_name,
                domain=lead.domain,
                industry=lead.industry,
                company_summary=lead.company_summary,
                value_proposition=lead.value_proposition,
                icp_score=lead.icp_score,
                confidence_score=lead.confidence_score,
                geography=lead.geography,
                estimated_company_size=lead.estimated_company_size,
                status=lead.status,
                created_at=lead.created_at.isoformat(),
                similarity=round(sim, 4),
            )
            for _, sim, lead in top_items
        ]

        return HybridSearchResponse(
            query=clean_query,
            results=results,
            total=len(results),
            ranking_strategy="Hybrid score = 0.60 * Cosine Similarity + 0.25 * (ICP / 100) + 0.15 * Keyword Text Match",
        )

    async def get_lead(
        self,
        lead_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves full lead details, signals, source crawled pages, embedding metadata, and audit records."""
        lead_stmt = select(Lead).where(Lead.id == lead_id)
        if organization_id:
            lead_stmt = lead_stmt.where(
                or_(Lead.organization_id == organization_id, Lead.organization_id.is_(None))
            )
        lead_res = await self.db.execute(lead_stmt)
        lead = lead_res.scalar_one_or_none()
        if not lead:
            return None

        # Fetch signals
        sig_stmt = select(LeadSignal).where(LeadSignal.lead_id == lead.id).order_by(LeadSignal.created_at.asc())
        sig_res = await self.db.execute(sig_stmt)
        signals = sig_res.scalars().all()

        # Fetch source crawled pages from CrawledPage table
        pages_stmt = (
            select(CrawledPage)
            .where(CrawledPage.crawl_target_id == lead.crawl_target_id)
            .order_by(CrawledPage.depth.asc())
        )
        pages_res = await self.db.execute(pages_stmt)
        source_pages = pages_res.scalars().all()

        # Fetch embedding metadata (excluding raw float vector)
        emb_stmt = select(LeadEmbedding.id, LeadEmbedding.content, LeadEmbedding.content_hash, LeadEmbedding.created_at).where(
            LeadEmbedding.lead_id == lead.id
        )
        emb_res = await self.db.execute(emb_stmt)
        emb_row = emb_res.first()

        # Fetch audit logs
        audit_stmt = select(LLMAuditLog).where(LLMAuditLog.lead_id == lead.id).order_by(LLMAuditLog.created_at.desc())
        audit_res = await self.db.execute(audit_stmt)
        audit_logs = audit_res.scalars().all()

        # Extract positive and negative signals lists from qualification JSON
        q_json = lead.qualification_json or {}
        positives = q_json.get("positive_signals", [])
        negatives = q_json.get("negative_signals", [])

        return {
            "id": str(lead.id),
            "organization_id": str(lead.organization_id) if lead.organization_id else None,
            "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
            "crawl_target_id": str(lead.crawl_target_id),
            "company_name": lead.company_name,
            "domain": lead.domain,
            "company_summary": lead.company_summary,
            "value_proposition": lead.value_proposition,
            "industry": lead.industry,
            "target_audience": lead.target_audience,
            "business_model": lead.business_model,
            "geography": lead.geography,
            "estimated_company_size": lead.estimated_company_size,
            "technology_signals": lead.technology_signals,
            "icp_score": lead.icp_score,
            "confidence_score": lead.confidence_score,
            "status": lead.status,
            "qualification_reasoning": lead.qualification_reasoning,
            "qualification_json": lead.qualification_json,
            "positive_signals": positives,
            "negative_signals": negatives,
            "created_at": lead.created_at.isoformat(),
            "updated_at": lead.updated_at.isoformat(),
            "signals": [
                {
                    "id": str(s.id),
                    "signal": s.signal,
                    "evidence": s.evidence,
                    "source_url": s.source_url,
                    "sentiment": s.sentiment,
                    "created_at": s.created_at.isoformat(),
                }
                for s in signals
            ],
            "source_pages": [
                {
                    "id": str(p.id),
                    "url": p.url,
                    "final_url": p.final_url,
                    "title": p.title,
                    "depth": p.depth,
                    "status_code": p.status_code,
                    "fetched_at": p.fetched_at.isoformat(),
                }
                for p in source_pages
            ],
            "embedding": {
                "id": str(emb_row.id),
                "content_hash": emb_row.content_hash,
                "dimension": 1536,
                "indexed_hnsw": True,
                "created_at": emb_row.created_at.isoformat(),
            } if emb_row else None,
            "audit_logs": [
                {
                    "provider": a.provider,
                    "model": a.model,
                    "input_tokens": a.input_tokens,
                    "output_tokens": a.output_tokens,
                    "total_tokens": a.total_tokens,
                    "latency_ms": a.latency_ms,
                    "request_id": a.request_id,
                    "created_at": a.created_at.isoformat(),
                }
                for a in audit_logs
            ],
        }

    async def export_leads(
        self,
        format_type: str,
        search: Optional[str] = None,
        min_icp_score: Optional[int] = None,
        max_icp_score: Optional[int] = None,
        industry: Optional[str] = None,
        geography: Optional[str] = None,
        status: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        campaign_id: Optional[uuid.UUID] = None,
        limit: int = 1000,
    ) -> Any:
        """Exports filtered leads into CSV string or JSON-compatible list."""
        conditions = self._build_filter_conditions(
            search=search,
            min_icp_score=min_icp_score,
            max_icp_score=max_icp_score,
            industry=industry,
            geography=geography,
            status=status,
            organization_id=organization_id,
            campaign_id=campaign_id,
        )

        stmt = select(Lead)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(Lead.icp_score), desc(Lead.created_at)).limit(limit)

        res = await self.db.execute(stmt)
        leads = res.scalars().all()

        if format_type.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            # Required CSV export columns
            writer.writerow([
                "company_name",
                "domain",
                "industry",
                "geography",
                "icp_score",
                "confidence_score",
                "status",
                "company_summary",
                "value_proposition",
            ])
            for l in leads:
                writer.writerow([
                    l.company_name,
                    l.domain,
                    l.industry,
                    l.geography,
                    l.icp_score,
                    l.confidence_score,
                    l.status,
                    l.company_summary,
                    l.value_proposition,
                ])
            return output.getvalue()
        else:
            return [
                {
                    "company_name": l.company_name,
                    "domain": l.domain,
                    "industry": l.industry,
                    "geography": l.geography,
                    "icp_score": l.icp_score,
                    "confidence_score": l.confidence_score,
                    "status": l.status,
                    "company_summary": l.company_summary,
                    "value_proposition": l.value_proposition,
                }
                for l in leads
            ]

    async def seed_demo_leads(self) -> List[str]:
        """
        Seeds synthetic, clearly labelled demo leads into PostgreSQL with associated
        CrawlTarget, CrawledPages, LeadSignals, LeadEmbedding, and LLMAuditLog.
        Guarantees realistic B2B intelligence data for testing without external API calls.
        """
        demo_companies = [
            {
                "company_name": "[Demo] CloudFlow Ops",
                "domain": "cloudflow-demo.io",
                "url": "https://cloudflow-demo.io",
                "industry": "SaaS",
                "geography": "United States",
                "company_size": "51-200",
                "status": "QUALIFIED",
                "icp_score": 94,
                "confidence_score": 0.96,
                "summary": "CloudFlow Ops develops an autonomous cloud infrastructure orchestration platform for Kubernetes and microservices workflows.",
                "value_proposition": "Reduces enterprise cloud infrastructure costs by 40% with predictive auto-scaling and zero-downtime canary deployments.",
                "target_audience": "Enterprise DevOps teams, platform engineering directors, and VP Infrastructure.",
                "business_model": "B2B SaaS subscription with tier-based compute licensing.",
                "technologies": ["Kubernetes", "Terraform", "AWS", "Golang", "Prometheus"],
                "reasoning": "Strong match for enterprise B2B ICP: recurring SaaS revenue, 50-200 headcount, modern cloud-native stack, verified enterprise customer logos.",
                "signals": [
                    {
                        "signal": "Enterprise B2B SaaS Orchestration",
                        "evidence": "Our control plane connects to multi-cloud clusters to autonomously detect anomalies and heal pods before outages occur.",
                        "source_url": "https://cloudflow-demo.io/products/platform",
                        "sentiment": "positive",
                    },
                    {
                        "signal": "Tiered enterprise pricing & SOC2 compliance",
                        "evidence": "Enterprise plans include SOC2 Type II compliance, dedicated technical account management, and 99.99% uptime SLAs.",
                        "source_url": "https://cloudflow-demo.io/pricing",
                        "sentiment": "positive",
                    },
                ],
                "pages": [
                    {"url": "https://cloudflow-demo.io/", "title": "CloudFlow Ops — Autonomous Cloud Infrastructure", "depth": 0},
                    {"url": "https://cloudflow-demo.io/products/platform", "title": "Platform Overview | CloudFlow Ops", "depth": 1},
                    {"url": "https://cloudflow-demo.io/pricing", "title": "Enterprise Pricing & Plans | CloudFlow Ops", "depth": 1},
                ],
            },
            {
                "company_name": "[Demo] FinEdge Intelligence",
                "domain": "finedge-demo.com",
                "url": "https://finedge-demo.com",
                "industry": "FinTech",
                "geography": "United Kingdom",
                "company_size": "11-50",
                "status": "NEW",
                "icp_score": 88,
                "confidence_score": 0.92,
                "summary": "Real-time fraud prevention and transaction risk scoring API for neobanks and global payment gateways.",
                "value_proposition": "Sub-10ms risk classification using graph neural networks to stop payment fraud prior to card clearing.",
                "target_audience": "Fintech CTOs, heads of fraud risk, and compliance officers.",
                "business_model": "Usage-based B2B API pricing per transaction evaluated.",
                "technologies": ["Python", "Apache Kafka", "Redis", "Snowflake", "PyTorch"],
                "reasoning": "Excellent fit for fintech SaaS target. High transaction volume potential and rapid API self-service onboarding.",
                "signals": [
                    {
                        "signal": "Developer-first Risk API with native SDKs",
                        "evidence": "Integrate our risk engine in under 5 minutes with our official Python, TypeScript, and Go SDKs.",
                        "source_url": "https://finedge-demo.com/docs/api",
                        "sentiment": "positive",
                    },
                    {
                        "signal": "Global Banking Compliance Certifications",
                        "evidence": "Compliant with PSD2 SCA requirements and PCI-DSS Level 1 specifications.",
                        "source_url": "https://finedge-demo.com/security",
                        "sentiment": "positive",
                    },
                ],
                "pages": [
                    {"url": "https://finedge-demo.com/", "title": "FinEdge Intelligence — AI Fraud Defense", "depth": 0},
                    {"url": "https://finedge-demo.com/docs/api", "title": "API Documentation | FinEdge", "depth": 1},
                ],
            },
            {
                "company_name": "[Demo] LogiPulse Systems",
                "domain": "logipulse-demo.net",
                "url": "https://logipulse-demo.net",
                "industry": "Logistics",
                "geography": "Germany",
                "company_size": "51-200",
                "status": "REVIEW",
                "icp_score": 81,
                "confidence_score": 0.89,
                "summary": "IoT sensor telemetry and dynamic route optimization software for cold-chain pharmaceutical freight carriers.",
                "value_proposition": "Real-time temperature compliance and fuel optimization for cross-border temperature-sensitive shipping.",
                "target_audience": "Freight carrier fleet managers, pharma logistics directors.",
                "business_model": "Hybrid SaaS subscription plus IoT sensor hardware lease.",
                "technologies": ["IoT Telematics", "PostgreSQL", "React", "Rust"],
                "reasoning": "Fits enterprise mid-market logistics profile. Strong compliance hook with strict European cold-chain pharma regulations.",
                "signals": [
                    {
                        "signal": "Cold-Chain Fleet Telematics Software",
                        "evidence": "Fleet dispatchers track temperature variances in real-time across 10,000+ refrigerated trucks across the EU.",
                        "source_url": "https://logipulse-demo.net/fleet",
                        "sentiment": "positive",
                    },
                    {
                        "signal": "Hardware dependency in deployment",
                        "evidence": "Requires OBD-II gateway sensors installed in each vehicle before telemetry data can stream to dashboard.",
                        "source_url": "https://logipulse-demo.net/hardware",
                        "sentiment": "negative",
                    },
                ],
                "pages": [
                    {"url": "https://logipulse-demo.net/", "title": "LogiPulse — Smart Cold-Chain Fleet Telematics", "depth": 0},
                    {"url": "https://logipulse-demo.net/fleet", "title": "Fleet Management | LogiPulse", "depth": 1},
                ],
            },
            {
                "company_name": "[Demo] Apex Security Labs",
                "domain": "apexsec-demo.org",
                "url": "https://apexsec-demo.org",
                "industry": "Cybersecurity",
                "geography": "United States",
                "company_size": "51-200",
                "status": "CONTACTED",
                "icp_score": 91,
                "confidence_score": 0.95,
                "summary": "Automated continuous penetration testing and external attack surface management for regulated financial and healthcare institutions.",
                "value_proposition": "Identifies exploitable perimeter vulnerabilities with zero false-positives before adversaries strike.",
                "target_audience": "CISOs, security operations leads, VP Engineering.",
                "business_model": "Annual B2B SaaS enterprise contract.",
                "technologies": ["FastAPI", "Go", "Docker", "Nuclei", "AWS"],
                "reasoning": "High-urgency cybersecurity solution with substantial average contract value and proven executive buying committee.",
                "signals": [
                    {
                        "signal": "Autonomous Continuous Penetration Testing",
                        "evidence": "Safe, non-disruptive red-teaming scans executed continuously across IP ranges and cloud assets.",
                        "source_url": "https://apexsec-demo.org/platform",
                        "sentiment": "positive",
                    },
                    {
                        "signal": "Clear enterprise procurement process",
                        "evidence": "Schedule an external perimeter penetration assessment with our senior security consultants.",
                        "source_url": "https://apexsec-demo.org/contact",
                        "sentiment": "positive",
                    },
                ],
                "pages": [
                    {"url": "https://apexsec-demo.org/", "title": "Apex Security — Continuous Automated Pentesting", "depth": 0},
                    {"url": "https://apexsec-demo.org/platform", "title": "Platform Capabilities | Apex Security", "depth": 1},
                ],
            },
            {
                "company_name": "[Demo] TalentForge AI",
                "domain": "talentforge-demo.ai",
                "url": "https://talentforge-demo.ai",
                "industry": "HR Tech",
                "geography": "Canada",
                "company_size": "11-50",
                "status": "NEW",
                "icp_score": 73,
                "confidence_score": 0.84,
                "summary": "AI-assisted technical screening platform with automated code analysis and structured rubric scoring.",
                "value_proposition": "Cut engineering interviewing hours by 65% while eliminating interviewer bias.",
                "target_audience": "Engineering hiring managers and technical recruiters.",
                "business_model": "Tiered monthly subscription per active candidate seat.",
                "technologies": ["Next.js", "Python", "OpenAI", "PostgreSQL"],
                "reasoning": "Moderate fit for target. Lower contract value than enterprise infrastructure, but high velocity adoption in tech startups.",
                "signals": [
                    {
                        "signal": "Subscription pricing for mid-market engineering teams",
                        "evidence": "Plans start at $499/mo for up to 50 active candidate technical assessments.",
                        "source_url": "https://talentforge-demo.ai/pricing",
                        "sentiment": "positive",
                    },
                ],
                "pages": [
                    {"url": "https://talentforge-demo.ai/", "title": "TalentForge AI — Technical Screening Automated", "depth": 0},
                    {"url": "https://talentforge-demo.ai/pricing", "title": "Pricing & Plans | TalentForge", "depth": 1},
                ],
            },
            {
                "company_name": "[Demo] PureNature Essentials",
                "domain": "purenature-demo.store",
                "url": "https://purenature-demo.store",
                "industry": "eCommerce",
                "geography": "United States",
                "company_size": "1-10",
                "status": "REJECTED",
                "icp_score": 28,
                "confidence_score": 0.93,
                "summary": "Direct-to-consumer organic skincare, soaps, and home aromatherapy products.",
                "value_proposition": "Handcrafted organic essential oils shipped directly to your doorstep with zero synthetic chemicals.",
                "target_audience": "Health-conscious individual consumers and families.",
                "business_model": "B2C DTC eCommerce store.",
                "technologies": ["Shopify", "Klaviyo"],
                "reasoning": "Disqualified: Pure B2C DTC retail brand with zero B2B or SaaS characteristics. Does not meet target criteria.",
                "signals": [
                    {
                        "signal": "B2C Consumer Goods Retailer",
                        "evidence": "Shop our best-selling organic lavender body scrubs and essential oil diffusers with free domestic shipping on orders over $50.",
                        "source_url": "https://purenature-demo.store/shop",
                        "sentiment": "negative",
                    },
                    {
                        "signal": "No enterprise or B2B software offering",
                        "evidence": "Add products directly to consumer cart for single checkout via credit card or Apple Pay.",
                        "source_url": "https://purenature-demo.store/cart",
                        "sentiment": "negative",
                    },
                ],
                "pages": [
                    {"url": "https://purenature-demo.store/", "title": "PureNature Essentials — Organic Botanicals & Oils", "depth": 0},
                    {"url": "https://purenature-demo.store/shop", "title": "Shop Botanical Scrubs | PureNature", "depth": 1},
                ],
            },
        ]

        created_lead_ids: List[str] = []

        for item in demo_companies:
            # Check or create CrawlTarget
            t_stmt = select(CrawlTarget).where(CrawlTarget.domain == item["domain"])
            t_res = await self.db.execute(t_stmt)
            target = t_res.scalar_one_or_none()

            if not target:
                target = CrawlTarget(
                    url=item["url"],
                    normalized_url=item["url"],
                    domain=item["domain"],
                    status="completed",
                )
                self.db.add(target)
                await self.db.flush()

            # Pages
            for page_info in item["pages"]:
                p_stmt = select(CrawledPage).where(CrawledPage.url == page_info["url"])
                p_res = await self.db.execute(p_stmt)
                page = p_res.scalar_one_or_none()
                if not page:
                    page = CrawledPage(
                        crawl_target_id=target.id,
                        url=page_info["url"],
                        final_url=page_info["url"],
                        depth=page_info["depth"],
                        status_code=200,
                        title=page_info["title"],
                        content_markdown=f"# {page_info['title']}\n\n{item['summary']}\n\n{item['value_proposition']}",
                        content_hash=compute_content_hash(page_info["url"]),
                        page_metadata={"source": "demo_seed"},
                    )
                    self.db.add(page)

            await self.db.flush()

            # Qualification structure
            qualification = CompanyQualification(
                company_name=item["company_name"],
                company_summary=item["summary"],
                value_proposition=item["value_proposition"],
                industry=item["industry"],
                target_audience=item["target_audience"],
                products_or_services=[item["industry"] + " Platform"],
                business_model=item["business_model"],
                geography=item["geography"],
                estimated_company_size=item["company_size"],
                technology_signals=item["technologies"],
                contact_signals={"contact_page": f"{item['url']}/contact"},
                icp_score=item["icp_score"],
                confidence_score=item["confidence_score"],
                positive_signals=[s["signal"] for s in item["signals"] if s["sentiment"] == "positive"],
                negative_signals=[s["signal"] for s in item["signals"] if s["sentiment"] == "negative"],
                qualification_reasoning=item["reasoning"],
                signals=[
                    QualificationSignal(
                        signal=s["signal"],
                        evidence=s["evidence"],
                        source_url=s["source_url"],
                        sentiment=s["sentiment"],
                    )
                    for s in item["signals"]
                ],
            )

            # Check or create Lead
            l_stmt = select(Lead).where(Lead.crawl_target_id == target.id)
            l_res = await self.db.execute(l_stmt)
            lead = l_res.scalar_one_or_none()

            if not lead:
                lead = Lead(
                    crawl_target_id=target.id,
                    company_name=item["company_name"],
                    domain=item["domain"],
                    company_summary=item["summary"],
                    value_proposition=item["value_proposition"],
                    industry=item["industry"],
                    target_audience=item["target_audience"],
                    business_model=item["business_model"],
                    geography=item["geography"],
                    estimated_company_size=item["company_size"],
                    technology_signals=item["technologies"],
                    icp_score=item["icp_score"],
                    confidence_score=item["confidence_score"],
                    qualification_reasoning=item["reasoning"],
                    qualification_json=qualification.model_dump(),
                    status=item["status"],
                )
                self.db.add(lead)
                await self.db.flush()
            else:
                lead.company_name = item["company_name"]
                lead.company_summary = item["summary"]
                lead.value_proposition = item["value_proposition"]
                lead.industry = item["industry"]
                lead.target_audience = item["target_audience"]
                lead.business_model = item["business_model"]
                lead.geography = item["geography"]
                lead.estimated_company_size = item["company_size"]
                lead.technology_signals = item["technologies"]
                lead.icp_score = item["icp_score"]
                lead.confidence_score = item["confidence_score"]
                lead.status = item["status"]
                lead.qualification_reasoning = item["reasoning"]
                lead.qualification_json = qualification.model_dump()
                await self.db.flush()
                await self.db.execute(delete(LeadSignal).where(LeadSignal.lead_id == lead.id))

            # Add signals
            for s in item["signals"]:
                lead_sig = LeadSignal(
                    lead_id=lead.id,
                    signal=s["signal"],
                    evidence=s["evidence"],
                    source_url=s["source_url"],
                    sentiment=s["sentiment"],
                )
                self.db.add(lead_sig)

            # Add or update embedding
            canonical_doc = build_canonical_embedding_document(qualification)
            emb_hash = compute_content_hash(canonical_doc)
            emb_vector = await self.embedding_provider.generate_embedding(canonical_doc)

            emb_stmt = select(LeadEmbedding).where(LeadEmbedding.lead_id == lead.id)
            emb_res = await self.db.execute(emb_stmt)
            existing_emb = emb_res.scalar_one_or_none()

            if not existing_emb:
                new_emb = LeadEmbedding(
                    lead_id=lead.id,
                    content=canonical_doc,
                    content_hash=emb_hash,
                    embedding=emb_vector,
                )
                self.db.add(new_emb)
            else:
                existing_emb.content = canonical_doc
                existing_emb.content_hash = emb_hash
                existing_emb.embedding = emb_vector

            # LLM Audit
            audit_stmt = select(LLMAuditLog).where(LLMAuditLog.lead_id == lead.id)
            audit_res = await self.db.execute(audit_stmt)
            if not audit_res.scalar_one_or_none():
                audit = LLMAuditLog(
                    lead_id=lead.id,
                    provider="mock_seed" if self.embedding_provider.dimension == 1536 else "openai",
                    model="gpt-4o-mini-demo",
                    input_tokens=1420,
                    output_tokens=380,
                    total_tokens=1800,
                    latency_ms=850.5,
                    request_id=f"demo-{uuid.uuid4().hex[:8]}",
                )
                self.db.add(audit)

            created_lead_ids.append(str(lead.id))

        await self.db.commit()
        logger.info("Successfully seeded %d demo leads.", len(created_lead_ids))
        return created_lead_ids
