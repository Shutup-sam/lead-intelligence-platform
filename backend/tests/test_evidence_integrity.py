import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import QualificationPipeline
from app.ai.llm_provider import BaseLLMProvider, LLMExecutionResult, MockLLMProvider
from app.ai.embeddings import BaseEmbeddingProvider
from app.ai.models import CompanyQualification
from app.models.crawl import CrawlTarget, CrawledPage
from app.models.lead import Lead, LeadSignal
from app.services.lead_service import LeadService


def create_mock_embedding_provider():
    mock_emb = MagicMock(spec=BaseEmbeddingProvider)
    mock_emb.dimension = 1536
    mock_emb.generate_embedding = AsyncMock(return_value=[0.05] * 1536)
    return mock_emb


@pytest.mark.asyncio
async def test_choiceindia_cannot_receive_example_com_evidence():
    """
    Requirement 11A: choiceindia.com cannot receive example.com evidence.
    Even if an LLM outputs example.com URLs for choiceindia.com,
    the pipeline must strip them and refuse to accept them.
    """
    mock_emb = create_mock_embedding_provider()
    pipeline = QualificationPipeline(embedding_provider=mock_emb)

    pages = [
        {
            "url": "https://choiceindia.com/",
            "title": "Choice - Stock Broker in India",
            "content_markdown": "Choice is a full-service stock broker in India offering online trading in stocks, mutual funds, derivatives.",
            "depth": 0,
        }
    ]

    # Run default MockLLMProvider against choiceindia.com
    qual, _, _, _, _ = await pipeline.qualify(
        domain="choiceindia.com",
        target_url="https://choiceindia.com/",
        crawled_pages=pages,
    )

    # 1. No example.com anywhere in signals or grounded attributes
    for sig in qual.signals:
        assert sig.source_url is not None
        assert "example.com" not in sig.source_url.lower(), f"Forbidden example.com found in signal: {sig.source_url}"
        assert "choiceindia.com" in sig.source_url.lower()

    for attr, field in qual.grounded_attributes.items():
        if field.source_url:
            assert "example.com" not in field.source_url.lower(), f"Forbidden example.com in attribute {attr}: {field.source_url}"

    # 2. Company size must be Unknown (not 51-200)
    assert qual.estimated_company_size == "Unknown"
    # 3. Technology signals must be empty (not PostgreSQL/React)
    assert qual.technology_signals == []
    # 4. Geography must be India, not North America
    assert qual.geography == "India"
    assert "India" in qual.company_summary or "India" in qual.industry or "India" in qual.geography


@pytest.mark.asyncio
async def test_valid_evidence_must_point_to_actual_crawled_page():
    """
    Requirement 11F: Valid evidence must point to an actual crawled page stored for this target.
    If evidence points to a page that was never fetched by Scrapling, it must be rejected.
    """
    mock_emb = create_mock_embedding_provider()

    fake_payload = {
        "company_name": "Test Co",
        "company_summary": "Test Co summary.",
        "value_proposition": "Value prop.",
        "industry": "FinTech",
        "target_audience": "Banks",
        "products_or_services": [],
        "business_model": "Unknown",
        "geography": "Unknown",
        "estimated_company_size": "Unknown",
        "technology_signals": [],
        "contact_signals": {},
        "icp_score": 40,
        "confidence_score": 0.7,
        "positive_signals": [],
        "negative_signals": [],
        "qualification_reasoning": "Reasoning.",
        "signals": [
            {
                "signal": "Un-crawled Subpage Signal",
                "evidence": "Some verified quote from another un-crawled page.",
                "source_url": "https://testco.com/hidden-page-not-in-db",
                "sentiment": "positive",
                "status": "observed",
                "confidence": 0.8,
            }
        ],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=fake_payload,
            provider="mock-test",
            model="test-v1",
            input_tokens=50,
            output_tokens=50,
            total_tokens=100,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    actual_crawled_pages = [
        {
            "url": "https://testco.com/",
            "title": "Test Co Home",
            "content_markdown": "Welcome to Test Co. Some verified quote from another un-crawled page.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("testco.com", "https://testco.com/", actual_crawled_pages)

    # Since https://testco.com/hidden-page-not-in-db was never crawled, the signal MUST be rejected!
    assert len(qual.signals) == 0


@pytest.mark.asyncio
async def test_cross_company_evidence_contamination_prevented():
    """
    Requirement 11B: Evidence from Company A cannot appear in Company B's dossier.
    """
    mock_emb = create_mock_embedding_provider()

    # Synthetic LLM that tries to inject Company A's evidence into Company B
    fake_payload = {
        "company_name": "Company B Tech",
        "company_summary": "Company B operations overview.",
        "value_proposition": "Company B value proposition.",
        "industry": "Enterprise Software",
        "target_audience": "Enterprise CIOs",
        "products_or_services": [],
        "business_model": "Unknown",
        "geography": "Unknown",
        "estimated_company_size": "Unknown",
        "technology_signals": [],
        "contact_signals": {},
        "icp_score": 50,
        "confidence_score": 0.8,
        "positive_signals": [],
        "negative_signals": [],
        "qualification_reasoning": "Evaluation with cross-company injection.",
        "signals": [
            {
                "signal": "Contaminated signal from Company A",
                "evidence": "Company A patented proprietary machine learning algorithms.",
                "source_url": "https://company-a.com/technology",
                "sentiment": "positive",
                "status": "observed",
                "confidence": 0.95,
            }
        ],
        "observed_facts": [
            "Proprietary tech cited from Company A (URL: https://company-a.com/technology)"
        ],
        "inferred_signals": [],
        "unknown_attributes": ["estimated_company_size"],
        "grounded_attributes": {
            "technology_signals": {
                "value": "Machine Learning",
                "status": "observed",
                "confidence": 0.95,
                "evidence": "Company A patented proprietary machine learning algorithms.",
                "source_url": "https://company-a.com/technology",
            }
        },
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=fake_payload,
            provider="mock-test",
            model="test-v1",
            input_tokens=100,
            output_tokens=100,
            total_tokens=200,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    company_b_pages = [
        {
            "url": "https://company-b.com/",
            "title": "Company B Home",
            "content_markdown": "Welcome to Company B. We build business software.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("company-b.com", "https://company-b.com/", company_b_pages)

    # Cross-company signal from company-a.com MUST be rejected!
    assert len(qual.signals) == 0, f"Cross-company signal was not rejected: {qual.signals}"
    assert len(qual.observed_facts) == 0, f"Cross-company observed fact was not rejected: {qual.observed_facts}"
    assert qual.grounded_attributes["technology_signals"].status == "unknown"
    assert qual.grounded_attributes["technology_signals"].source_url is None


@pytest.mark.asyncio
async def test_fake_url_rejected():
    """
    Requirement 11C & 11F: Fake URL generated by the LLM that was not fetched by Scrapling is rejected.
    """
    mock_emb = create_mock_embedding_provider()

    fake_payload = {
        "company_name": "Acme Corp",
        "company_summary": "Acme summary.",
        "value_proposition": "Acme value.",
        "industry": "Logistics",
        "target_audience": "Shippers",
        "products_or_services": [],
        "business_model": "Unknown",
        "geography": "Unknown",
        "estimated_company_size": "Unknown",
        "technology_signals": [],
        "contact_signals": {},
        "icp_score": 50,
        "confidence_score": 0.8,
        "positive_signals": [],
        "negative_signals": [],
        "qualification_reasoning": "Reasoning.",
        "signals": [
            {
                "signal": "Invented Page Signal",
                "evidence": "Acme delivers next-day freight across all fifty states.",
                "source_url": "https://acme.com/invented-404-subpage-never-crawled",
                "sentiment": "positive",
                "status": "observed",
                "confidence": 0.9,
            }
        ],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=fake_payload,
            provider="mock-test",
            model="test-v1",
            input_tokens=50,
            output_tokens=50,
            total_tokens=100,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    actual_crawled_pages = [
        {
            "url": "https://acme.com/",
            "title": "Acme Home",
            "content_markdown": "Acme delivers next-day freight across all fifty states.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("acme.com", "https://acme.com/", actual_crawled_pages)

    # Signal citing un-crawled URL must be rejected
    assert len(qual.signals) == 0


@pytest.mark.asyncio
async def test_fake_quote_rejected():
    """
    Requirement 11D: Fake quote not present in crawled content is rejected.
    """
    mock_emb = create_mock_embedding_provider()

    fake_payload = {
        "company_name": "Acme Corp",
        "company_summary": "Acme summary.",
        "value_proposition": "Acme value.",
        "industry": "Logistics",
        "target_audience": "Shippers",
        "products_or_services": [],
        "business_model": "Unknown",
        "geography": "Unknown",
        "estimated_company_size": "Unknown",
        "technology_signals": [],
        "contact_signals": {},
        "icp_score": 50,
        "confidence_score": 0.8,
        "positive_signals": [],
        "negative_signals": [],
        "qualification_reasoning": "Reasoning.",
        "signals": [
            {
                "signal": "Hallucinated Headcount Claim",
                "evidence": "We employ over 10,000 certified engineers globally across 40 countries.",  # Not in crawled markdown!
                "source_url": "https://acme.com/",  # Valid URL, but fake quote
                "sentiment": "positive",
                "status": "observed",
                "confidence": 0.9,
            }
        ],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=fake_payload,
            provider="mock-test",
            model="test-v1",
            input_tokens=50,
            output_tokens=50,
            total_tokens=100,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    actual_crawled_pages = [
        {
            "url": "https://acme.com/",
            "title": "Acme Home",
            "content_markdown": "Welcome to Acme Logistics. We manage local freight and regional trucking routes.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("acme.com", "https://acme.com/", actual_crawled_pages)

    # Signal with fake quote must be rejected!
    assert len(qual.signals) == 0


@pytest.mark.asyncio
async def test_valid_quote_accepted():
    """
    Requirement 11E: Valid quote from an actual crawled page is accepted.
    """
    mock_emb = create_mock_embedding_provider()

    valid_payload = {
        "company_name": "Choice",
        "company_summary": "Choice is one of the best stock brokers in India.",
        "value_proposition": "Online trading in stocks and derivatives.",
        "industry": "Financial Services",
        "target_audience": "Investors",
        "products_or_services": ["Stock Trading"],
        "business_model": "Brokerage",
        "geography": "India",
        "estimated_company_size": "Unknown",
        "technology_signals": [],
        "contact_signals": {},
        "icp_score": 25,
        "confidence_score": 0.9,
        "positive_signals": [],
        "negative_signals": [],
        "qualification_reasoning": "Reasoning.",
        "signals": [
            {
                "signal": "Stock Brokerage in India",
                "evidence": "Choice (formerly Choice Broking) is one of the best stock brokers in India.",
                "source_url": "https://choiceindia.com/",
                "sentiment": "neutral",
                "status": "observed",
                "confidence": 1.0,
            }
        ],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=valid_payload,
            provider="mock-test",
            model="test-v1",
            input_tokens=50,
            output_tokens=50,
            total_tokens=100,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    crawled_pages = [
        {
            "url": "https://choiceindia.com/",
            "title": "Choice - Stock Broker in India",
            "content_markdown": "Choice (formerly Choice Broking) is one of the best stock brokers in India. Start online trading in stocks.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("choiceindia.com", "https://choiceindia.com/", crawled_pages)

    # Valid quote on valid page MUST be accepted
    assert len(qual.signals) == 1
    assert qual.signals[0].signal == "Stock Brokerage in India"
    assert qual.signals[0].source_url == "https://choiceindia.com/"


@pytest.mark.asyncio
async def test_cross_domain_evidence_rejected():
    """
    Requirement 11G: Cross-domain evidence (e.g. citing third-party or competitor domain) is rejected.
    """
    mock_emb = create_mock_embedding_provider()

    payload_with_cross_domain = {
        "company_name": "Target Co",
        "company_summary": "Target company summary.",
        "value_proposition": "Value prop.",
        "industry": "FinTech",
        "target_audience": "Banks",
        "products_or_services": [],
        "business_model": "Unknown",
        "geography": "Unknown",
        "estimated_company_size": "Unknown",
        "technology_signals": [],
        "contact_signals": {},
        "icp_score": 40,
        "confidence_score": 0.7,
        "positive_signals": [],
        "negative_signals": [],
        "qualification_reasoning": "Reasoning.",
        "signals": [
            {
                "signal": "Cross Domain Signal",
                "evidence": "Some text that happens to match.",
                "source_url": "https://competitor.com/product",
                "sentiment": "positive",
                "status": "observed",
                "confidence": 0.8,
            }
        ],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=payload_with_cross_domain,
            provider="mock-test",
            model="test-v1",
            input_tokens=50,
            output_tokens=50,
            total_tokens=100,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    crawled_pages = [
        {
            "url": "https://target.com/",
            "title": "Target Co Home",
            "content_markdown": "Some text that happens to match.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("target.com", "https://target.com/", crawled_pages)

    # Signal citing competitor.com must be rejected
    assert len(qual.signals) == 0


@pytest.mark.asyncio
async def test_unknown_claims_remain_unknown_instead_of_fabricated():
    """
    Requirement 11H: Attributes with no evidence in crawled content (headcount, tech, geography)
    must remain Unknown or empty instead of being fabricated.
    """
    mock_emb = create_mock_embedding_provider()

    hallucinated_payload = {
        "company_name": "Simple Blog",
        "company_summary": "Personal musings and recipes.",
        "value_proposition": "Great recipes.",
        "industry": "Publishing",
        "target_audience": "Home Cooks",
        "products_or_services": ["Enterprise Recipe Cloud Engine", "Culinary API"],  # Fabricated!
        "business_model": "B2B SaaS Subscription",  # Fabricated!
        "geography": "North America",  # Fabricated!
        "estimated_company_size": "500+",  # Fabricated!
        "technology_signals": ["Kubernetes", "PostgreSQL", "React"],  # Fabricated!
        "contact_signals": {},
        "icp_score": 80,
        "confidence_score": 0.9,
        "positive_signals": [],
        "negative_signals": [],
        "qualification_reasoning": "Reasoning.",
        "signals": [],
    }

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_qualification = AsyncMock(
        return_value=LLMExecutionResult(
            data=hallucinated_payload,
            provider="mock-test",
            model="test-v1",
            input_tokens=50,
            output_tokens=50,
            total_tokens=100,
            latency_ms=10.0,
        )
    )

    pipeline = QualificationPipeline(llm_provider=mock_llm, embedding_provider=mock_emb)

    blog_pages = [
        {
            "url": "https://simpleblog.net/",
            "title": "My Recipe Blog",
            "content_markdown": "Welcome to my home cooking diary. Today we bake bread with yeast, water, and flour.",
            "depth": 0,
        }
    ]

    qual, _, _, _, _ = await pipeline.qualify("simpleblog.net", "https://simpleblog.net/", blog_pages)

    # All unsupported attributes MUST be reset to Unknown / empty
    assert qual.estimated_company_size == "Unknown"
    assert qual.technology_signals == []
    assert qual.products_or_services == []
    assert qual.geography == "Unknown"
    assert qual.business_model == "Unknown"
    assert "estimated_company_size" in qual.unknown_attributes
    assert "technology_signals" in qual.unknown_attributes
    assert "products_or_services" in qual.unknown_attributes
    assert "geography" in qual.unknown_attributes
    assert "business_model" in qual.unknown_attributes
