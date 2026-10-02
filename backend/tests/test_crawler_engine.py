import pytest
from unittest.mock import AsyncMock, MagicMock
from app.crawler.fetcher import ScraplingFetcher, FetchResult
from app.crawler.robots import RobotsPolicy
from app.crawler.crawler import WebsiteCrawler


MOCK_HOMEPAGE = """
<html>
<head><title>TestBiz Homepage</title></head>
<body>
    <h1>Welcome to TestBiz</h1>
    <p>AI Enterprise Lead Discovery.</p>
    <a href="/about">About Us</a>
    <a href="/pricing">Pricing Plans</a>
    <a href="/services">Our Services</a>
    <a href="/careers">Careers</a>
    <a href="/contact">Contact Us</a>
    <a href="https://external-competitor.com/blog">Offsite Link</a>
</body>
</html>
"""

MOCK_ABOUT = """
<html>
<head><title>About TestBiz</title></head>
<body>
    <h1>About Our Company</h1>
    <p>Founded in 2024 to modernize lead generation.</p>
    <a href="mailto:founder@testbiz.com">Email Us</a>
</body>
</html>
"""

MOCK_SERVICES = """
<html>
<head><title>TestBiz Services</title></head>
<body>
    <h1>Services & Solutions</h1>
    <p>High-precision web data extraction and pipeline automation.</p>
</body>
</html>
"""

MOCK_PRICING = """
<html>
<head><title>TestBiz Pricing</title></head>
<body>
    <h1>Transparent Pricing</h1>
    <p>Plans starting at $99/mo.</p>
</body>
</html>
"""

MOCK_CONTACT = """
<html>
<head><title>Contact TestBiz</title></head>
<body>
    <h1>Contact Our Sales Team</h1>
    <p>Call us today at <a href="tel:+15550199999">+1 (555) 019-9999</a>.</p>
</body>
</html>
"""

# Duplicate of MOCK_ABOUT to test deduplication
MOCK_DUPLICATE_ABOUT = """
<html>
<head><title>Duplicate Page</title></head>
<body>
    <h1>About Our Company</h1>
    <p>Founded in 2024 to modernize lead generation.</p>
    <a href="mailto:founder@testbiz.com">Email Us</a>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_crawler_engine_bfs_and_prioritization():
    mock_pages = {
        "https://testbiz.com/": MOCK_HOMEPAGE,
        "https://testbiz.com/about": MOCK_ABOUT,
        "https://testbiz.com/services": MOCK_SERVICES,
        "https://testbiz.com/pricing": MOCK_PRICING,
        "https://testbiz.com/contact": MOCK_CONTACT,
    }

    async def mock_fetch(url: str):
        content = mock_pages.get(url, "<html><body>Not Found</body></html>")
        status = 200 if url in mock_pages else 404
        return FetchResult(
            url=url,
            final_url=url,
            status_code=status,
            content=content,
            response_time_ms=12.5,
        )

    mock_fetcher = MagicMock(spec=ScraplingFetcher)
    mock_fetcher.fetch = AsyncMock(side_effect=mock_fetch)

    # Allow all in robots.txt
    mock_robots = MagicMock(spec=RobotsPolicy)
    mock_robots.fetch_and_parse = AsyncMock(return_value=(True, "allowed"))
    mock_robots.is_allowed = MagicMock(return_value=(True, "allowed"))

    crawler = WebsiteCrawler(
        fetcher=mock_fetcher,
        robots_policy=mock_robots,
        max_pages=4,
        max_depth=2,
    )

    results, discovered_count, failed_count = await crawler.crawl_site("https://testbiz.com")

    # Verify max_pages cap enforced
    assert len(results) == 4
    assert failed_count == 0

    urls_crawled = [r.url for r in results]
    # Homepage was crawled first
    assert urls_crawled[0] == "https://testbiz.com/"
    # Offsite link was not crawled (same-domain restriction)
    assert not any("external-competitor.com" in u for u in urls_crawled)

    # Discovered count includes links from homepage
    assert discovered_count >= 5

    # Metadata extraction on crawled pages
    about_result = next((r for r in results if r.url == "https://testbiz.com/about"), None)
    if about_result:
        assert "founder@testbiz.com" in about_result.emails


@pytest.mark.asyncio
async def test_crawler_deduplication():
    # Crawl with identical content bodies
    mock_pages = {
        "https://testbiz.com/": "<html><body><a href='/page1'>P1</a><a href='/page2'>P2</a></body></html>",
        "https://testbiz.com/page1": MOCK_ABOUT,
        "https://testbiz.com/page2": MOCK_DUPLICATE_ABOUT,  # Identical content
    }

    async def mock_fetch(url: str):
        content = mock_pages.get(url, "")
        return FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content=content,
            response_time_ms=5.0,
        )

    mock_fetcher = MagicMock(spec=ScraplingFetcher)
    mock_fetcher.fetch = AsyncMock(side_effect=mock_fetch)

    mock_robots = MagicMock(spec=RobotsPolicy)
    mock_robots.fetch_and_parse = AsyncMock(return_value=(True, "allowed"))
    mock_robots.is_allowed = MagicMock(return_value=(True, "allowed"))

    crawler = WebsiteCrawler(
        fetcher=mock_fetcher,
        robots_policy=mock_robots,
        max_pages=10,
        max_depth=2,
    )

    results, _, _ = await crawler.crawl_site("https://testbiz.com")
    # Should have crawled homepage and page1, while skipping duplicate page2
    assert len(results) == 2
    urls = [r.url for r in results]
    assert "https://testbiz.com/page2" not in urls
