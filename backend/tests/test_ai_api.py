import pytest
import uuid
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from app.ai.models import LeadQualifyResponse


@pytest.mark.asyncio
async def test_qualify_api_success(client: AsyncClient):
    target_id = uuid.uuid4()
    lead_id = uuid.uuid4()

    mock_resp = LeadQualifyResponse(
        lead_id=str(lead_id),
        company_name="Apex Logic",
        domain="apexlogic.io",
        icp_score=85,
        confidence_score=0.92,
        signals_count=3,
        embedding_created=True,
        llm_provider="mock",
        llm_model="mock-v1",
        duration_seconds=0.45,
    )

    with patch(
        "app.api.v1.leads.LeadService.qualify_target",
        new=AsyncMock(return_value=mock_resp),
    ):
        response = await client.post(
            f"/api/v1/leads/qualify/{target_id}",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["lead_id"] == str(lead_id)
        assert data["company_name"] == "Apex Logic"
        assert data["icp_score"] == 85
        assert data["embedding_created"] is True


@pytest.mark.asyncio
async def test_qualify_api_target_not_found(client: AsyncClient):
    target_id = uuid.uuid4()

    with patch(
        "app.api.v1.leads.LeadService.qualify_target",
        new=AsyncMock(side_effect=ValueError(f"CrawlTarget with ID '{target_id}' not found.")),
    ):
        response = await client.post(f"/api/v1/leads/qualify/{target_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_lead_details_success(client: AsyncClient):
    lead_id = uuid.uuid4()
    mock_lead_dict = {
        "id": str(lead_id),
        "crawl_target_id": str(uuid.uuid4()),
        "company_name": "Apex Logic",
        "domain": "apexlogic.io",
        "company_summary": "Autonomous sales workflows.",
        "value_proposition": "Cut sales cycle duration.",
        "industry": "B2B SaaS",
        "target_audience": "Mid-market software teams",
        "business_model": "SaaS Subscription",
        "geography": "United States",
        "estimated_company_size": "51-200",
        "technology_signals": ["PostgreSQL", "React"],
        "icp_score": 85,
        "confidence_score": 0.92,
        "qualification_reasoning": "Strong match with target criteria.",
        "qualification_json": {},
        "created_at": "2026-10-02T16:00:00Z",
        "updated_at": "2026-10-02T16:00:00Z",
        "signals": [
            {
                "id": str(uuid.uuid4()),
                "signal": "B2B SaaS model",
                "evidence": "Tiered monthly pricing plans.",
                "source_url": "https://apexlogic.io/pricing",
                "sentiment": "positive",
                "created_at": "2026-10-02T16:00:00Z",
            }
        ],
        "embedding": {
            "id": str(uuid.uuid4()),
            "content_hash": "hash_abc_123",
            "dimension": 1536,
            "indexed_hnsw": True,
            "created_at": "2026-10-02T16:00:00Z",
        },
        "audit_logs": [
            {
                "provider": "mock",
                "model": "mock-v1",
                "input_tokens": 150,
                "output_tokens": 80,
                "total_tokens": 230,
                "latency_ms": 32.5,
                "request_id": "req-001",
                "created_at": "2026-10-02T16:00:00Z",
            }
        ],
    }

    with patch(
        "app.api.v1.leads.LeadService.get_lead",
        new=AsyncMock(return_value=mock_lead_dict),
    ):
        response = await client.get(f"/api/v1/leads/{lead_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(lead_id)
        assert data["company_name"] == "Apex Logic"
        assert len(data["signals"]) == 1
        assert data["embedding"]["dimension"] == 1536
        assert data["embedding"]["indexed_hnsw"] is True
        # Verify raw vector is NOT exposed in the standard API response
        assert "embedding_vector" not in data["embedding"]
        assert "raw_vector" not in data["embedding"]


@pytest.mark.asyncio
async def test_get_lead_details_not_found(client: AsyncClient):
    lead_id = uuid.uuid4()
    with patch(
        "app.api.v1.leads.LeadService.get_lead",
        new=AsyncMock(return_value=None),
    ):
        response = await client.get(f"/api/v1/leads/{lead_id}")
        assert response.status_code == 404
