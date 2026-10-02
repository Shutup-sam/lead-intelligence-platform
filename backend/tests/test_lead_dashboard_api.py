import uuid
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from app.schemas.lead import (
    LeadListResponse,
    LeadListItem,
    SemanticSearchResponse,
    SemanticSearchResultItem,
    HybridSearchResponse,
)


@pytest.mark.asyncio
async def test_lead_pagination(client: AsyncClient):
    mock_resp = LeadListResponse(
        items=[
            LeadListItem(
                lead_id=str(uuid.uuid4()),
                crawl_target_id=str(uuid.uuid4()),
                company_name="CloudFlow Ops",
                domain="cloudflow.io",
                industry="SaaS",
                company_summary="Cloud infrastructure automation",
                value_proposition="Reduces cloud costs by 40%",
                icp_score=94,
                confidence_score=0.95,
                geography="United States",
                estimated_company_size="51-200",
                status="NEW",
                created_at="2026-10-02T12:00:00Z",
            )
        ],
        page=1,
        page_size=25,
        total=1,
        pages=1,
    )

    with patch("app.api.v1.leads.LeadService.list_leads", new=AsyncMock(return_value=mock_resp)):
        res = await client.get("/api/v1/leads?page=1&page_size=25")
        assert res.status_code == 200
        data = res.json()
        assert data["page"] == 1
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["company_name"] == "CloudFlow Ops"


@pytest.mark.asyncio
async def test_lead_filters(client: AsyncClient):
    with patch("app.api.v1.leads.LeadService.list_leads", new=AsyncMock()) as mock_list:
        mock_list.return_value = LeadListResponse(items=[], page=1, page_size=25, total=0, pages=0)

        res = await client.get("/api/v1/leads?min_icp_score=80&industry=FinTech&status=QUALIFIED")
        assert res.status_code == 200

        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        assert kwargs["min_icp_score"] == 80
        assert kwargs["industry"] == "FinTech"
        assert kwargs["status"] == "QUALIFIED"


@pytest.mark.asyncio
async def test_lead_sorting(client: AsyncClient):
    with patch("app.api.v1.leads.LeadService.list_leads", new=AsyncMock()) as mock_list:
        mock_list.return_value = LeadListResponse(items=[], page=1, page_size=25, total=0, pages=0)

        res = await client.get("/api/v1/leads?sort_by=icp_score&sort_order=desc")
        assert res.status_code == 200

        _, kwargs = mock_list.call_args
        assert kwargs["sort_by"] == "icp_score"
        assert kwargs["sort_order"] == "desc"


@pytest.mark.asyncio
async def test_lead_status_update_success(client: AsyncClient):
    lead_id = uuid.uuid4()
    mock_lead = AsyncMock()
    mock_lead.id = lead_id
    mock_lead.status = "QUALIFIED"
    mock_lead.updated_at = AsyncMock()
    mock_lead.updated_at.isoformat = lambda: "2026-10-02T12:00:00Z"

    with patch("app.api.v1.leads.LeadService.update_lead_status", new=AsyncMock(return_value=mock_lead)):
        res = await client.patch(
            f"/api/v1/leads/{lead_id}/status",
            json={"status": "QUALIFIED"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["lead_id"] == str(lead_id)
        assert data["status"] == "QUALIFIED"


@pytest.mark.asyncio
async def test_lead_status_update_invalid_enum(client: AsyncClient):
    lead_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/leads/{lead_id}/status",
        json={"status": "UNKNOWN_STATUS"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_lead_status_update_not_found(client: AsyncClient):
    lead_id = uuid.uuid4()
    with patch("app.api.v1.leads.LeadService.update_lead_status", new=AsyncMock(return_value=None)):
        res = await client.patch(
            f"/api/v1/leads/{lead_id}/status",
            json={"status": "REVIEW"},
        )
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_semantic_search_success(client: AsyncClient):
    mock_resp = SemanticSearchResponse(
        query="enterprise devops orchestration",
        results=[
            SemanticSearchResultItem(
                lead_id=str(uuid.uuid4()),
                company_name="CloudFlow Ops",
                domain="cloudflow.io",
                industry="SaaS",
                company_summary="Devops orchestration",
                icp_score=94,
                confidence_score=0.96,
                geography="United States",
                status="QUALIFIED",
                similarity=0.88,
            )
        ],
        count=1,
    )

    with patch("app.api.v1.leads.LeadService.semantic_search", new=AsyncMock(return_value=mock_resp)):
        res = await client.post(
            "/api/v1/leads/search/semantic",
            json={"query": "enterprise devops orchestration", "limit": 10},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "enterprise devops orchestration"
        assert len(data["results"]) == 1
        assert data["results"][0]["similarity"] == 0.88


@pytest.mark.asyncio
async def test_semantic_search_empty_query(client: AsyncClient):
    res = await client.post(
        "/api/v1/leads/search/semantic",
        json={"query": "", "limit": 10},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_hybrid_search_with_query(client: AsyncClient):
    mock_resp = HybridSearchResponse(
        query="fraud prevention api",
        results=[
            LeadListItem(
                lead_id=str(uuid.uuid4()),
                crawl_target_id=str(uuid.uuid4()),
                company_name="FinEdge",
                domain="finedge.com",
                industry="FinTech",
                company_summary="Fraud prevention API",
                value_proposition="Sub-10ms risk classification",
                icp_score=88,
                confidence_score=0.92,
                geography="United Kingdom",
                estimated_company_size="11-50",
                status="NEW",
                created_at="2026-10-02T12:00:00Z",
                similarity=0.82,
            )
        ],
        total=1,
        ranking_strategy="Hybrid score = 0.60 * Cosine Similarity + 0.25 * (ICP / 100) + 0.15 * Keyword Text Match",
    )

    with patch("app.api.v1.leads.LeadService.hybrid_search", new=AsyncMock(return_value=mock_resp)):
        res = await client.get("/api/v1/leads/search?q=fraud+prevention+api&min_icp_score=75")
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "fraud prevention api"
        assert "Hybrid score" in data["ranking_strategy"]
        assert len(data["results"]) == 1
        assert data["results"][0]["similarity"] == 0.82


@pytest.mark.asyncio
async def test_csv_export(client: AsyncClient):
    csv_data = "company_name,domain,industry,geography,icp_score,confidence_score,status,company_summary,value_proposition\nCloudFlow,cloudflow.io,SaaS,United States,94,0.96,NEW,Summary,Value Prop\n"
    with patch("app.api.v1.leads.LeadService.export_leads", new=AsyncMock(return_value=csv_data)):
        res = await client.get("/api/v1/leads/export.csv?min_icp_score=80")
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]
        assert "leads_export.csv" in res.headers["content-disposition"]
        assert "company_name,domain,industry" in res.text


@pytest.mark.asyncio
async def test_json_export(client: AsyncClient):
    json_data = [
        {
            "company_name": "CloudFlow",
            "domain": "cloudflow.io",
            "industry": "SaaS",
            "geography": "United States",
            "icp_score": 94,
            "confidence_score": 0.96,
            "status": "NEW",
            "company_summary": "Summary",
            "value_proposition": "Value Prop",
        }
    ]
    with patch("app.api.v1.leads.LeadService.export_leads", new=AsyncMock(return_value=json_data)):
        res = await client.get("/api/v1/leads/export.json?status=NEW")
        assert res.status_code == 200
        assert "application/json" in res.headers["content-type"]
        assert "leads_export.json" in res.headers["content-disposition"]
        data = res.json()
        assert len(data) == 1
        assert data[0]["company_name"] == "CloudFlow"


@pytest.mark.asyncio
async def test_lead_detail_with_source_pages(client: AsyncClient):
    lead_id = uuid.uuid4()
    mock_detail = {
        "id": str(lead_id),
        "crawl_target_id": str(uuid.uuid4()),
        "company_name": "CloudFlow Ops",
        "domain": "cloudflow.io",
        "company_summary": "Autonomous cloud infrastructure",
        "value_proposition": "Cut cloud costs 40%",
        "industry": "SaaS",
        "target_audience": "Enterprise DevOps",
        "business_model": "B2B SaaS",
        "geography": "United States",
        "estimated_company_size": "51-200",
        "technology_signals": ["Kubernetes", "AWS"],
        "icp_score": 94,
        "confidence_score": 0.96,
        "status": "QUALIFIED",
        "qualification_reasoning": "Strong enterprise ICP fit.",
        "qualification_json": {},
        "positive_signals": ["Enterprise SaaS"],
        "negative_signals": [],
        "created_at": "2026-10-02T12:00:00Z",
        "updated_at": "2026-10-02T12:00:00Z",
        "signals": [
            {
                "id": str(uuid.uuid4()),
                "signal": "Enterprise SaaS",
                "evidence": "Our control plane connects to multi-cloud clusters.",
                "source_url": "https://cloudflow.io/products",
                "sentiment": "positive",
                "created_at": "2026-10-02T12:00:00Z",
            }
        ],
        "source_pages": [
            {
                "id": str(uuid.uuid4()),
                "url": "https://cloudflow.io/",
                "final_url": "https://cloudflow.io/",
                "title": "CloudFlow Ops Home",
                "depth": 0,
                "status_code": 200,
                "fetched_at": "2026-10-02T12:00:00Z",
            }
        ],
        "embedding": {
            "id": str(uuid.uuid4()),
            "content_hash": "abc123hash",
            "dimension": 1536,
            "indexed_hnsw": True,
            "created_at": "2026-10-02T12:00:00Z",
        },
        "audit_logs": [
            {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "input_tokens": 1200,
                "output_tokens": 300,
                "total_tokens": 1500,
                "latency_ms": 780.0,
                "request_id": "req-123",
                "created_at": "2026-10-02T12:00:00Z",
            }
        ],
    }

    with patch("app.api.v1.leads.LeadService.get_lead", new=AsyncMock(return_value=mock_detail)):
        res = await client.get(f"/api/v1/leads/{lead_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["company_name"] == "CloudFlow Ops"
        assert len(data["source_pages"]) == 1
        assert data["source_pages"][0]["title"] == "CloudFlow Ops Home"
        assert len(data["signals"]) == 1
        assert data["embedding"]["dimension"] == 1536
        assert "embedding_vector" not in data  # Raw vector omitted


@pytest.mark.asyncio
async def test_seed_demo_endpoint(client: AsyncClient):
    with patch("app.api.v1.leads.LeadService.seed_demo_leads", new=AsyncMock(return_value=["id1", "id2"])):
        res = await client.post("/api/v1/leads/seed-demo")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 2
