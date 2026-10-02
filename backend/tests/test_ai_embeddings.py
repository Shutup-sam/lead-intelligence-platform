import math
import pytest
from app.ai.models import CompanyQualification
from app.ai.embeddings import (
    build_canonical_embedding_document,
    compute_content_hash,
    MockEmbeddingProvider,
)


@pytest.mark.asyncio
async def test_canonical_document_and_content_hash():
    qual = CompanyQualification(
        company_name="CloudMatrix",
        company_summary="Enterprise cloud migration and Kubernetes operations.",
        value_proposition="Cut multi-cloud infrastructure overhead by 30%.",
        industry="Cloud Infrastructure",
        target_audience="VP of Engineering and DevOps Managers",
        products_or_services=["MatrixMesh", "CloudCost API"],
        business_model="B2B Enterprise License",
        geography="North America",
        estimated_company_size="100-250",
        technology_signals=["Kubernetes", "AWS", "Terraform"],
        icp_score=90,
        confidence_score=0.95,
        positive_signals=["Matches cloud B2B profile", "Enterprise scale"],
        negative_signals=[],
        qualification_reasoning="Strong alignment with enterprise criteria.",
        signals=[],
    )

    doc = build_canonical_embedding_document(qual)
    assert "Company:\nCloudMatrix" in doc
    assert "Industry:\nCloud Infrastructure" in doc
    assert "Value proposition:\nCut multi-cloud" in doc
    assert "MatrixMesh, CloudCost API" in doc

    h1 = compute_content_hash(doc)
    h2 = compute_content_hash(doc)
    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_mock_embedding_provider_dimension_and_idempotency():
    provider = MockEmbeddingProvider(dimension=1536)
    assert provider.dimension == 1536

    text_sample = "Company: CloudMatrix\nIndustry: Cloud Infrastructure"

    # Generate vector
    vec1 = await provider.generate_embedding(text_sample)
    vec2 = await provider.generate_embedding(text_sample)

    # Correct dimension
    assert len(vec1) == 1536
    assert len(vec2) == 1536

    # Idempotent determinism: identical text produces identical vector
    assert vec1 == vec2

    # Different text produces different vector
    vec3 = await provider.generate_embedding("Company: OtherCorp\nIndustry: Consumer")
    assert vec1 != vec3

    # Normalized unit length (L2 norm ~ 1.0)
    norm = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(norm, rel=1e-3) == 1.0
