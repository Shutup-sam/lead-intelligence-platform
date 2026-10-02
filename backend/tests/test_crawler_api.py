import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from app.crawler.models import CrawlSummaryResult, CrawlPageResult


@pytest.mark.asyncio
async def test_crawl_api_success(client: AsyncClient):
    mock_summary = CrawlSummaryResult(
        target_id="11111111-2222-3333-4444-555555555555",
        target_url="https://valid-target.com",
        normalized_url="https://valid-target.com/",
        domain="valid-target.com",
        status="completed",
        pages_discovered=4,
        pages_crawled=2,
        pages_failed=0,
        emails_found=1,
        phones_found=1,
        duration_seconds=1.2,
        robots_status="allowed",
        crawled_pages=[
            CrawlPageResult(
                url="https://valid-target.com/",
                final_url="https://valid-target.com/",
                status_code=200,
                depth=0,
                title="Target Homepage",
                content_markdown="# Target Homepage\nLeading AI solutions.",
                content_hash="mockhash123",
                emails=["sales@valid-target.com"],
                phones=["+1-800-555-0199"],
            )
        ],
    )

    with patch(
        "app.api.v1.crawl.CrawlService.execute_crawl",
        new=AsyncMock(return_value=mock_summary),
    ):
        response = await client.post(
            "/api/v1/crawl",
            json={"url": "https://valid-target.com", "max_pages": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["domain"] == "valid-target.com"
        assert data["pages_crawled"] == 2
        assert data["emails_found"] == 1
        assert len(data["crawled_pages"]) == 1


@pytest.mark.asyncio
async def test_crawl_api_ssrf_rejection(client: AsyncClient):
    # Attempting to target internal addresses must return 400 Bad Request
    response = await client.post(
        "/api/v1/crawl",
        json={"url": "http://127.0.0.1:8000/internal"},
    )
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "SSRF" in detail or "private/reserved" in detail


@pytest.mark.asyncio
async def test_crawl_api_invalid_scheme(client: AsyncClient):
    response = await client.post(
        "/api/v1/crawl",
        json={"url": "file:///etc/passwd"},
    )
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "Unsupported scheme" in detail or "Invalid URL" in detail
