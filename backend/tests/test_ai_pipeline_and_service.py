import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.ai.pipeline import QualificationPipeline
from app.ai.llm_provider import BaseLLMProvider, LLMExecutionResult
from app.ai.embeddings import BaseEmbeddingProvider
from app.ai.models import ICPProfile
from app.services.lead_service import LeadService
from app.models.crawl import CrawlTarget, CrawledPage


@pytest.mark.asyncio
async def test_qualification_pipeline_success():
    mock_data = {
        "company_name": "PipelineAI",
        "company_summary": "Autonomous B2B data pipelines.",
        "value_proposition": "Cut ingestion latency to milliseconds.",
        "industry": "Data Engineering",
        "target_audience": "Enterprise Data Engineers",
        "products_or_services": ["PipelineSync", "FastLoader"],
        "business_model": "SaaS Subscription",
        "geography": "Global",
        "estimated_company_size": "11-50",
        "technology_signals": ["Kafka", "ClickHouse"],
        "contact_signals": {"emails": ["contact@pipelineai.io"]},
        "icp_score": 92,
        "confidence_score": 0.95,
        "positive_signals": ["Clear B2B product", "High technical depth"],
        "negative_signals": [],
        "qualification_reasoning": "Excellent fit for data engineering ICP.",
        "signals": [
            {
                "signal": "B2B SaaS product",
                "evidence": "Pricing plans list tiered software subscriptions.",
                "source_url": "https://pipelineai.io/pricing",
                "sentiment": "positive",
            }
        ],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=mock_data,
            provider="mock-llm",
            model="mock-v1",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            latency_ms=25.0,
            request_id="req-123",
        )
    )

    mock_emb = MagicMock(spec=BaseEmbeddingProvider)
    mock_emb.dimension = 1536
    mock_emb.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    pages = [
        {
            "url": "https://pipelineai.io/about",
            "title": "About PipelineAI",
            "content_markdown": "# About PipelineAI\nWe deliver enterprise data pipelines.",
            "content_hash": "hash_about_01",
            "depth": 0,
            "metadata": {},
        }
    ]

    qual, canon_doc, emb_hash, vec, audit = await pipeline.qualify(
        domain="pipelineai.io",
        target_url="https://pipelineai.io/",
        crawled_pages=pages,
    )

    assert qual.company_name == "PipelineAI"
    assert qual.icp_score == 92
    assert len(vec) == 1536
    assert len(emb_hash) == 64
    assert audit.input_tokens == 100
    assert audit.output_tokens == 50


@pytest.mark.asyncio
async def test_qualification_pipeline_malformed_llm_output():
    # LLM returns invalid data (e.g. missing company_name and out of range score)
    malformed_data = {
        "company_summary": "Missing company_name and invalid score",
        "icp_score": 9999,
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=malformed_data,
            provider="mock-llm",
            model="mock-v1",
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm)
    pages = [{"url": "https://bad.com", "content_markdown": "Bad content", "depth": 0}]

    with pytest.raises(ValueError, match="Invalid LLM qualification output schema"):
        await pipeline.qualify("bad.com", "https://bad.com", pages)


@pytest.mark.asyncio
async def test_qualification_pipeline_empty_crawl_data():
    pipeline = QualificationPipeline()
    with pytest.raises(ValueError, match="No crawled pages available"):
        await pipeline.qualify("empty.com", "https://empty.com", [])


@pytest.mark.asyncio
async def test_lead_service_target_not_found():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    service = LeadService(db=mock_db)
    random_id = uuid.uuid4()

    with pytest.raises(ValueError, match="not found"):
        await service.qualify_target(random_id)


@pytest.mark.asyncio
async def test_hallucination_prevention_on_educational_demo_sandbox():
    """
    Regression test: When crawled site contains only 'Educational demo sandbox for scraping.',
    the AI pipeline must strictly ground attributes and NEVER invent commercial products,
    headcount, business models, geography, or technologies.
    """
    mock_emb = MagicMock(spec=BaseEmbeddingProvider)
    mock_emb.dimension = 1536
    mock_emb.generate_embedding = AsyncMock(return_value=[0.05] * 1536)

    # Use default MockLLMProvider
    pipeline = QualificationPipeline(embedding_provider=mock_emb)

    pages = [
        {
            "url": "https://sandbox.test/",
            "title": "Scraping Sandbox",
            "content_markdown": "Educational demo sandbox for scraping.",
            "content_hash": "hash_sandbox_001",
            "depth": 0,
            "metadata": {},
        }
    ]

    qual, canon_doc, emb_hash, vec, audit = await pipeline.qualify(
        domain="sandbox.test",
        target_url="https://sandbox.test/",
        crawled_pages=pages,
    )

    # 1. Commercial products = unknown / empty list
    assert qual.products_or_services == [], f"Expected empty products, got {qual.products_or_services}"

    # 2. Employee count = unknown
    assert qual.estimated_company_size == "Unknown", f"Expected 'Unknown' size, got {qual.estimated_company_size}"

    # 3. Business model = unknown / non-commercial
    assert "unknown" in qual.business_model.lower() or "non-commercial" in qual.business_model.lower()

    # 4. Technology stack = unknown / empty list
    assert qual.technology_signals == [], f"Expected empty tech signals, got {qual.technology_signals}"

    # 5. Geography = unknown
    assert qual.geography == "Unknown", f"Expected 'Unknown' geography, got {qual.geography}"

    # 6. Qualification uses the negative evidence that actually exists
    assert qual.icp_score <= 25, f"Expected low ICP score for demo sandbox, got {qual.icp_score}"
    assert len(qual.negative_signals) > 0, "Expected negative signals documenting lack of commercial B2B offerings"
    assert any(s.sentiment == "negative" for s in qual.signals), "Expected negative evidence signals"

    # 7. Explicit separation of facts, inferences, and unknowns
    assert len(qual.unknown_attributes) >= 4
    assert "estimated_company_size" in qual.unknown_attributes
    assert "products_or_services" in qual.unknown_attributes
    assert "technology_signals" in qual.unknown_attributes
    assert len(qual.observed_facts) > 0
    assert len(qual.inferred_signals) > 0


@pytest.mark.asyncio
async def test_hallucination_prevention_sanitizes_unsupported_llm_hallucinations():
    """
    Regression test: Even if an LLM returns fabricated claims for an educational sandbox,
    the QualificationPipeline._enforce_evidence_grounding step must sanitize unsupported fields.
    """
    fabricated_data = {
        "company_name": "Demo Sandbox",
        "company_summary": "Educational demo sandbox for scraping.",
        "value_proposition": "World leading autonomous AI platform",  # Hallucinated
        "industry": "Enterprise Tech",
        "target_audience": "Fortune 500 CEOs",
        "products_or_services": ["Autonomous AI Bot", "Cloud Pipeline"],  # Hallucinated
        "business_model": "B2B Subscription / SaaS",  # Hallucinated
        "geography": "North America",  # Hallucinated
        "estimated_company_size": "51-200",  # Hallucinated
        "technology_signals": ["PostgreSQL", "React"],  # Hallucinated
        "contact_signals": {},
        "icp_score": 15,
        "confidence_score": 0.9,
        "positive_signals": [],
        "negative_signals": ["Educational demo only"],
        "qualification_reasoning": "Demo site without commercial operations.",
        "signals": [
            {
                "signal": "Demo sandbox",
                "evidence": "Educational demo sandbox for scraping.",
                "source_url": "https://sandbox.test/",
                "sentiment": "negative",
            }
        ],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=fabricated_data,
            provider="mock-llm",
            model="mock-v1",
            input_tokens=100,
            output_tokens=100,
            total_tokens=200,
            latency_ms=15.0,
        )
    )

    mock_emb = MagicMock(spec=BaseEmbeddingProvider)
    mock_emb.dimension = 1536
    mock_emb.generate_embedding = AsyncMock(return_value=[0.1] * 1536)

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    pages = [
        {
            "url": "https://sandbox.test/",
            "title": "Sandbox Test",
            "content_markdown": "Educational demo sandbox for scraping.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("sandbox.test", "https://sandbox.test/", pages)

    # Verify sanitizer stripped all hallucinations
    assert qual.products_or_services == []
    assert qual.estimated_company_size == "Unknown"
    assert qual.technology_signals == []
    assert "unknown" in qual.business_model.lower() or "non-commercial" in qual.business_model.lower()
    assert qual.geography == "Unknown"
    assert "estimated_company_size" in qual.unknown_attributes
    assert "products_or_services" in qual.unknown_attributes

